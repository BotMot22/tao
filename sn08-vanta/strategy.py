"""
SN8 Vanta × Jane Quant Agent Bridge
=====================================
Pipes Jane's 26-factor alpha signals into the Vanta miner REST API.

Jane (localhost:8080) → this bridge → Vanta miner (localhost:8088)

Signal mapping:
  Jane "long"    → Vanta "LONG"
  Jane "short"   → Vanta "SHORT"
  Position close → Vanta "FLAT"

Asset mapping:
  Jane BTC  → Vanta BTCUSD
  Jane SOL  → Vanta SOLUSD

Vanta scoring: 100% Avg Daily PnL
Elimination: >10% max drawdown = permanent ban
Challenge period: 61-90 trading days
"""

import json
import time
import logging
import requests
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/root/tao/sn08-vanta/bridge.log"),
    ],
)
log = logging.getLogger("jane-vanta-bridge")

# --- Configuration ---

# Jane quant agent
JANE_API = os.getenv("JANE_API", "http://127.0.0.1:8080")
JANE_STATE_FILE = Path("/root/jane/data/jane_state.json")

# Vanta miner
VANTA_API = os.getenv("VANTA_API", "http://127.0.0.1:8088")
VANTA_API_KEY = os.getenv("VANTA_API_KEY", "CHANGE_ME_TO_A_SECURE_RANDOM_STRING")

# Asset mapping: Jane ticker → Vanta trade pair
ASSET_MAP = {
    "BTC": "BTCUSD",
    "SOL": "SOLUSD",
    # AVAX not available on Vanta
    # ETH could be added if Jane adds it
}

# --- Risk Management (phi framework adapted for Vanta) ---
# Vanta eliminates at 10% drawdown — we must be conservative

# Max leverage per position (Vanta crypto limit: 0.01x-2.5x)
MAX_LEVERAGE = 0.5  # Conservative — survival > returns during challenge

# Portfolio leverage cap (Vanta crypto limit: 5x)
MAX_PORTFOLIO_LEVERAGE = 1.5

# Minimum alpha score to forward signal (Jane default: 0.50)
MIN_ALPHA_SCORE = 0.50

# Minimum confidence to forward signal (Jane default: 0.50)
MIN_CONFIDENCE = 0.50

# Scale leverage by alpha strength: leverage = base × strength_multiplier
# strength = score × confidence (0 to 1.0)
BASE_LEVERAGE = 0.1  # 10% of portfolio at minimum signal
LEVERAGE_SCALE = 0.4  # Additional leverage scaled by strength

# Cooldown between signals per pair (seconds)
SIGNAL_COOLDOWN = 300  # 5 min (Vanta has 5s minimum)

# Use bracket orders with stop-loss and take-profit
USE_BRACKET_ORDERS = True

# Poll interval (seconds)
POLL_INTERVAL = 30


@dataclass
class VantaPosition:
    """Track what we've sent to Vanta."""
    pair: str
    direction: str  # LONG | SHORT
    leverage: float
    timestamp: float
    jane_position_id: str


class JaneVantaBridge:
    """Bridge Jane's alpha signals to Vanta miner API."""

    def __init__(self):
        self.active_positions: dict[str, VantaPosition] = {}  # pair → position
        self.last_signal_time: dict[str, float] = {}  # pair → timestamp
        self.total_leverage = 0.0

    def get_jane_state(self) -> dict | None:
        """Fetch Jane's current state via REST API or state file."""
        # Try REST API first
        try:
            resp = requests.get(f"{JANE_API}/api/state", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            pass

        # Fallback to state file
        try:
            if JANE_STATE_FILE.exists():
                return json.loads(JANE_STATE_FILE.read_text())
        except Exception as e:
            log.error(f"Failed to read Jane state: {e}")

        return None

    def get_jane_positions(self) -> list[dict]:
        """Get Jane's current crypto positions."""
        state = self.get_jane_state()
        if not state:
            return []

        positions = state.get("positions", [])
        # Filter to crypto_spot only (what Vanta supports)
        return [
            p for p in positions
            if p.get("market_type") == "crypto_spot"
            and p.get("asset") in ASSET_MAP
        ]

    def compute_leverage(self, position: dict) -> float:
        """
        Compute Vanta leverage from Jane's signal strength.

        Jane provides:
          - alpha_score (-1 to +1) in metadata
          - confidence (0 to 1) in metadata
          - vol-targeted size in $

        We map strength to leverage conservatively.
        """
        metadata = position.get("metadata", {})
        alpha_score = abs(metadata.get("alpha_score", 0.5))
        confidence = metadata.get("alpha_confidence", 0.5)

        # Strength = score × confidence (0 to 1)
        strength = alpha_score * confidence

        # Scale leverage: base + (strength × scale)
        leverage = BASE_LEVERAGE + (strength * LEVERAGE_SCALE)

        # Cap at max
        leverage = min(leverage, MAX_LEVERAGE)

        # Check portfolio limit
        remaining = MAX_PORTFOLIO_LEVERAGE - self.total_leverage
        leverage = min(leverage, remaining)

        return round(max(leverage, 0.01), 3)  # Vanta minimum: 0.01x

    def submit_to_vanta(
        self,
        trade_pair: str,
        order_type: str,
        leverage: float = 0.0,
        execution_type: str = "MARKET",
        **kwargs,
    ) -> dict | None:
        """Submit order to Vanta miner API."""
        payload = {
            "execution_type": execution_type,
            "trade_pair": trade_pair,
            "order_type": order_type,
            "leverage": leverage,
            **kwargs,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": VANTA_API_KEY,
        }

        try:
            resp = requests.post(
                f"{VANTA_API}/api/submit-order",
                json=payload,
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
            log.info(f"VANTA ORDER: {trade_pair} {order_type} {leverage}x → {result}")
            return result
        except requests.exceptions.RequestException as e:
            log.error(f"Vanta order failed: {e}")
            return None

    def open_position(self, jane_pos: dict) -> bool:
        """Open a position on Vanta based on Jane's signal."""
        asset = jane_pos["asset"]
        pair = ASSET_MAP[asset]
        direction = jane_pos["side"].upper()  # "long" → "LONG"

        # Check cooldown
        now = time.time()
        last = self.last_signal_time.get(pair, 0)
        if now - last < SIGNAL_COOLDOWN:
            log.debug(f"Cooldown active for {pair}, skipping")
            return False

        # Compute leverage
        leverage = self.compute_leverage(jane_pos)
        if leverage <= 0:
            log.warning(f"No leverage available for {pair} (portfolio at limit)")
            return False

        # Check alpha thresholds
        metadata = jane_pos.get("metadata", {})
        score = abs(metadata.get("alpha_score", 0))
        confidence = metadata.get("alpha_confidence", 0)

        if score < MIN_ALPHA_SCORE or confidence < MIN_CONFIDENCE:
            log.debug(f"Signal too weak for {pair}: score={score:.2f} conf={confidence:.2f}")
            return False

        # Build order
        if USE_BRACKET_ORDERS and "stop_loss" in jane_pos and "target" in jane_pos:
            # Use bracket order with Jane's SL/TP levels
            result = self.submit_to_vanta(
                trade_pair=pair,
                order_type=direction,
                leverage=leverage,
                execution_type="BRACKET",
                limit_price=jane_pos.get("entry_price", jane_pos.get("current_price")),
                stop_loss=jane_pos["stop_loss"],
                take_profit=jane_pos["target"],
            )
        else:
            result = self.submit_to_vanta(
                trade_pair=pair,
                order_type=direction,
                leverage=leverage,
            )

        if result:
            self.active_positions[pair] = VantaPosition(
                pair=pair,
                direction=direction,
                leverage=leverage,
                timestamp=now,
                jane_position_id=jane_pos.get("id", ""),
            )
            self.total_leverage += leverage
            self.last_signal_time[pair] = now
            log.info(
                f"OPENED {pair} {direction} {leverage}x | "
                f"Jane score={score:.2f} conf={confidence:.2f} | "
                f"Portfolio leverage: {self.total_leverage:.2f}x"
            )
            return True

        return False

    def close_position(self, pair: str, reason: str = "") -> bool:
        """Close a Vanta position (go FLAT)."""
        result = self.submit_to_vanta(
            trade_pair=pair,
            order_type="FLAT",
            leverage=0.0,
        )

        if result and pair in self.active_positions:
            pos = self.active_positions.pop(pair)
            self.total_leverage = max(0, self.total_leverage - pos.leverage)
            log.info(f"CLOSED {pair} | reason={reason} | Portfolio leverage: {self.total_leverage:.2f}x")
            return True

        return False

    def sync_positions(self):
        """
        Main sync loop: compare Jane's positions with Vanta's.

        Actions:
        1. Jane has position, Vanta doesn't → OPEN on Vanta
        2. Jane closed position, Vanta still open → CLOSE on Vanta
        3. Jane flipped direction → CLOSE + OPEN on Vanta
        """
        jane_positions = self.get_jane_positions()

        # Build map of Jane's current positions by asset
        jane_by_pair: dict[str, dict] = {}
        for jp in jane_positions:
            pair = ASSET_MAP.get(jp["asset"])
            if pair:
                jane_by_pair[pair] = jp

        # Close positions Jane no longer holds
        for pair in list(self.active_positions.keys()):
            if pair not in jane_by_pair:
                self.close_position(pair, reason="jane_closed")

        # Open/update positions Jane holds
        for pair, jp in jane_by_pair.items():
            jane_direction = jp["side"].upper()

            if pair in self.active_positions:
                vanta_pos = self.active_positions[pair]

                # Direction flip? Close and reopen
                if vanta_pos.direction != jane_direction:
                    self.close_position(pair, reason="direction_flip")
                    self.open_position(jp)
                # Otherwise: position already synced, no action needed
            else:
                # New position from Jane
                self.open_position(jp)

    def run(self):
        """Main bridge loop."""
        log.info("=" * 60)
        log.info("JANE × VANTA BRIDGE")
        log.info("=" * 60)
        log.info(f"Jane API:     {JANE_API}")
        log.info(f"Jane state:   {JANE_STATE_FILE}")
        log.info(f"Vanta API:    {VANTA_API}")
        log.info(f"Asset map:    {ASSET_MAP}")
        log.info(f"Max leverage: {MAX_LEVERAGE}x per position")
        log.info(f"Max portfolio: {MAX_PORTFOLIO_LEVERAGE}x total")
        log.info(f"Min alpha:    {MIN_ALPHA_SCORE}")
        log.info(f"Min conf:     {MIN_CONFIDENCE}")
        log.info(f"Brackets:     {USE_BRACKET_ORDERS}")
        log.info(f"Poll interval: {POLL_INTERVAL}s")
        log.info("")
        log.info("WARNING: Vanta eliminates at 10% drawdown. Stay conservative.")
        log.info("Challenge period: 61-90 trading days before full rewards.")
        log.info("=" * 60)

        # Verify Jane is reachable
        state = self.get_jane_state()
        if state:
            log.info(f"Jane connected | Bankroll: ${state.get('bankroll', 0):,.2f} | "
                     f"Open: {state.get('n_open', 0)} | Win rate: {state.get('win_rate', 0):.0%}")
        else:
            log.warning("Jane not reachable — will retry on each cycle")

        cycle = 0
        while True:
            try:
                cycle += 1
                self.sync_positions()

                if cycle % 10 == 0:  # Log status every ~5 min
                    log.info(
                        f"Cycle {cycle} | Vanta positions: {len(self.active_positions)} | "
                        f"Portfolio leverage: {self.total_leverage:.2f}x"
                    )

            except KeyboardInterrupt:
                log.info("Shutting down bridge...")
                break
            except Exception as e:
                log.error(f"Bridge error: {e}", exc_info=True)

            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    bridge = JaneVantaBridge()
    bridge.run()
