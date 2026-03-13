"""
SN8 Vanta × Jane Quant Agent Bridge
=====================================
Pipes Jane's 26-factor alpha signals into the Vanta miner REST API.
Sends TAO mining updates through Jane's Telegram bot.

Jane (localhost:8080) → this bridge → Vanta miner (localhost:8088)
                                    → Jane Telegram bot (TAO updates)

Signal mapping:
  Jane "long"    → Vanta "LONG"
  Jane "short"   → Vanta "SHORT"
  Position close → Vanta "FLAT"

Asset mapping:
  Jane BTC  → Vanta BTCUSD
  Jane SOL  → Vanta SOLUSD
  Jane AVAX → Vanta SOLUSD (proxy — high-beta alt correlation)

Vanta scoring: 100% Avg Daily PnL
Elimination: >10% max drawdown = permanent ban
Challenge period: 61-90 trading days
"""

import json
import sys
import time
import logging
import requests
import subprocess
import os
from dataclasses import dataclass, field
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
VANTA_API_KEY = os.getenv("VANTA_API_KEY", "xc6gH8GIaG9z6JJ8G0ED8-io3w_fbJBtW16M55MvpVw")

# Bittensor wallet
WALLET_NAME = "tao_miner"
HOTKEY_NAME = "default"

# Asset mapping: Jane ticker → Vanta trade pair
ASSET_MAP = {
    "BTC": "BTCUSD",
    "SOL": "SOLUSD",
    "AVAX": "SOLUSD",  # Proxy: AVAX → SOLUSD (high-beta alt correlation)
    # ETH could be added if Jane adds it
}

# Assets that share a Vanta pair (proxy mappings)
# When multiple Jane assets map to the same Vanta pair, use the strongest signal
PROXY_ASSETS = {"AVAX": "SOLUSD"}  # AVAX proxied through SOL

# --- Risk Management (phi framework adapted for Vanta) ---
# Vanta eliminates at 10% drawdown — we must be conservative

# Max leverage per position (Vanta crypto limit: 0.01x-2.5x)
MAX_LEVERAGE = 0.5  # Conservative — survival > returns during challenge

# Portfolio leverage cap (Vanta crypto limit: 5x)
MAX_PORTFOLIO_LEVERAGE = 1.5

# Minimum alpha score to forward signal (lowered from 0.50 for more signals)
MIN_ALPHA_SCORE = 0.40

# Minimum confidence to forward signal (lowered from 0.50 for more signals)
MIN_CONFIDENCE = 0.40

# Scale leverage by alpha strength: leverage = base × strength_multiplier
# strength = score × confidence (0 to 1.0)
BASE_LEVERAGE = 0.1  # 10% of portfolio at minimum signal
LEVERAGE_SCALE = 0.4  # Additional leverage scaled by strength

# Cooldown between signals per pair (seconds)
SIGNAL_COOLDOWN = 120  # 2 min (Vanta has 5s minimum, faster reaction)

# Use bracket orders with stop-loss and take-profit
USE_BRACKET_ORDERS = True

# Poll interval (seconds)
POLL_INTERVAL = 30

# TAO status update interval (seconds) — sent via Telegram
TAO_UPDATE_INTERVAL = 3600  # Hourly

# State file for persistence across restarts
BRIDGE_STATE_FILE = Path("/root/tao/sn08-vanta/bridge_state.json")


# --- Telegram Integration (uses Jane's bot) ---

# Load Jane's telegram config
sys.path.insert(0, "/root/jane")
try:
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
except ImportError:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_tg_http = requests.Session()


def tg_send(message: str, parse_mode: str = "HTML") -> bool:
    """Send a message via Jane's Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.debug("Telegram not configured, skipping notification")
        return False
    try:
        r = _tg_http.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")
        return False


def get_tao_balance() -> dict:
    """Get TAO wallet balance and subnet info via btcli."""
    info = {"balance": 0.0, "registered": False, "uid": None, "incentive": 0.0, "rank": 0.0}
    try:
        result = subprocess.run(
            ["btcli", "wallet", "overview", "--wallet-name", WALLET_NAME, "--no-prompt"],
            capture_output=True, text=True, timeout=30,
            input="\n",
        )
        output = result.stdout + result.stderr
        # Parse balance
        for line in output.split("\n"):
            if "free balance" in line.lower():
                # Extract number from line like "Wallet free balance: 0.3105 τ"
                parts = line.split(":")
                if len(parts) > 1:
                    bal_str = parts[1].strip().split()[0].replace("‎", "").replace(",", "")
                    try:
                        info["balance"] = float(bal_str)
                    except ValueError:
                        pass
            if "netuid" in line.lower() or "subnet" in line.lower():
                info["registered"] = True
    except Exception as e:
        log.warning(f"btcli balance check failed: {e}")

    return info


def get_vanta_health() -> dict:
    """Check Vanta miner health."""
    try:
        resp = requests.get(f"{VANTA_API}/api/health", timeout=5)
        if resp.status_code == 200:
            return {"status": "online", "data": resp.json()}
    except Exception:
        pass
    return {"status": "offline"}


@dataclass
class VantaPosition:
    """Track what we've sent to Vanta."""
    pair: str
    direction: str  # LONG | SHORT
    leverage: float
    timestamp: float
    jane_position_id: str


@dataclass
class BridgeStats:
    """Track bridge performance for reporting."""
    orders_sent: int = 0
    orders_filled: int = 0
    orders_failed: int = 0
    positions_opened: int = 0
    positions_closed: int = 0
    direction_flips: int = 0
    start_time: float = field(default_factory=time.time)
    last_tao_update: float = 0.0

    def uptime_str(self) -> str:
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        if hours > 24:
            days = hours // 24
            hours = hours % 24
            return f"{days}d {hours}h {minutes}m"
        return f"{hours}h {minutes}m"


class JaneVantaBridge:
    """Bridge Jane's alpha signals to Vanta miner API."""

    def __init__(self):
        self.active_positions: dict[str, VantaPosition] = {}  # pair → position
        self.last_signal_time: dict[str, float] = {}  # pair → timestamp
        self.total_leverage = 0.0
        self.stats = BridgeStats()
        self._load_state()
        self._save_state()  # Ensure state file exists for monitoring

    def _load_state(self):
        """Load persisted bridge state."""
        try:
            if BRIDGE_STATE_FILE.exists():
                data = json.loads(BRIDGE_STATE_FILE.read_text())
                self.stats.orders_sent = data.get("orders_sent", 0)
                self.stats.orders_filled = data.get("orders_filled", 0)
                self.stats.positions_opened = data.get("positions_opened", 0)
                self.stats.positions_closed = data.get("positions_closed", 0)
                log.info(f"Loaded bridge state: {self.stats.orders_sent} orders sent")
        except Exception:
            pass

    def _save_state(self):
        """Persist bridge state."""
        try:
            data = {
                "orders_sent": self.stats.orders_sent,
                "orders_filled": self.stats.orders_filled,
                "orders_failed": self.stats.orders_failed,
                "positions_opened": self.stats.positions_opened,
                "positions_closed": self.stats.positions_closed,
                "direction_flips": self.stats.direction_flips,
                "active_positions": {
                    k: {"pair": v.pair, "direction": v.direction, "leverage": v.leverage}
                    for k, v in self.active_positions.items()
                },
                "total_leverage": self.total_leverage,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            BRIDGE_STATE_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.warning(f"Failed to save bridge state: {e}")

    def get_jane_state(self) -> dict | None:
        """Fetch Jane's current state via REST API or state file."""
        try:
            resp = requests.get(f"{JANE_API}/api/state", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            pass

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

        positions = state.get("crypto_positions", [])
        return [
            p for p in positions
            if p.get("asset") in ASSET_MAP
        ]

    def compute_leverage(self, position: dict) -> float:
        """Compute Vanta leverage from Jane's signal strength."""
        metadata = position.get("metadata", {})
        alpha_score = abs(metadata.get("alpha_score", 0.5))
        confidence = metadata.get("alpha_confidence", 0.5)

        strength = alpha_score * confidence
        leverage = BASE_LEVERAGE + (strength * LEVERAGE_SCALE)
        leverage = min(leverage, MAX_LEVERAGE)

        remaining = MAX_PORTFOLIO_LEVERAGE - self.total_leverage
        leverage = min(leverage, remaining)

        return round(max(leverage, 0.01), 3)

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

        self.stats.orders_sent += 1

        try:
            resp = requests.post(
                f"{VANTA_API}/api/submit-order",
                json=payload,
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
            self.stats.orders_filled += 1
            log.info(f"VANTA ORDER: {trade_pair} {order_type} {leverage}x → {result}")
            return result
        except requests.exceptions.RequestException as e:
            self.stats.orders_failed += 1
            log.error(f"Vanta order failed: {e}")
            return None

    def open_position(self, jane_pos: dict) -> bool:
        """Open a position on Vanta based on Jane's signal."""
        asset = jane_pos["asset"]
        pair = ASSET_MAP[asset]
        direction = jane_pos["side"].upper()

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
            self.stats.positions_opened += 1
            self._save_state()

            proxy_note = f" (via {asset})" if asset in PROXY_ASSETS else ""

            log.info(
                f"OPENED {pair}{proxy_note} {direction} {leverage}x | "
                f"Jane score={score:.2f} conf={confidence:.2f} | "
                f"Portfolio leverage: {self.total_leverage:.2f}x"
            )

            # Telegram notification
            tg_send(
                f"<b>TAO MINER — OPEN {direction}</b>\n"
                f"<b>{pair}</b>{proxy_note} {leverage}x\n"
                f"Alpha: {score:.2f} | Conf: {confidence:.2f}\n"
                f"Portfolio: {self.total_leverage:.2f}x leverage"
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
            self.stats.positions_closed += 1
            if reason == "direction_flip":
                self.stats.direction_flips += 1
            self._save_state()

            log.info(f"CLOSED {pair} | reason={reason} | Portfolio leverage: {self.total_leverage:.2f}x")

            tg_send(
                f"<b>TAO MINER — CLOSE</b>\n"
                f"{pair} {pos.direction} {pos.leverage}x\n"
                f"Reason: {reason}"
            )

            return True

        return False

    def _pick_strongest(self, positions: list[dict]) -> dict:
        """When multiple Jane assets map to the same Vanta pair, pick strongest signal."""
        if len(positions) == 1:
            return positions[0]
        # Score by alpha_score × confidence
        def strength(p):
            m = p.get("metadata", {})
            return abs(m.get("alpha_score", 0)) * m.get("alpha_confidence", 0)
        return max(positions, key=strength)

    def sync_positions(self):
        """
        Main sync loop: compare Jane's positions with Vanta's.

        Actions:
        1. Jane has position, Vanta doesn't → OPEN on Vanta
        2. Jane closed position, Vanta still open → CLOSE on Vanta
        3. Jane flipped direction → CLOSE + OPEN on Vanta

        When multiple Jane assets map to the same Vanta pair (e.g. AVAX→SOLUSD),
        the strongest signal wins.
        """
        jane_positions = self.get_jane_positions()

        # Group by Vanta pair — multiple Jane assets may map to same pair
        jane_by_pair: dict[str, list[dict]] = {}
        for jp in jane_positions:
            pair = ASSET_MAP.get(jp["asset"])
            if pair:
                jane_by_pair.setdefault(pair, []).append(jp)

        # Resolve conflicts: pick strongest signal per Vanta pair
        best_by_pair: dict[str, dict] = {}
        for pair, candidates in jane_by_pair.items():
            best = self._pick_strongest(candidates)
            best_by_pair[pair] = best
            if len(candidates) > 1:
                assets = [c["asset"] for c in candidates]
                log.info(f"Proxy conflict on {pair}: {assets} → using {best['asset']}")

        # Close positions Jane no longer holds
        for pair in list(self.active_positions.keys()):
            if pair not in best_by_pair:
                self.close_position(pair, reason="jane_closed")

        # Open/update positions Jane holds
        for pair, jp in best_by_pair.items():
            jane_direction = jp["side"].upper()

            if pair in self.active_positions:
                vanta_pos = self.active_positions[pair]
                if vanta_pos.direction != jane_direction:
                    self.close_position(pair, reason="direction_flip")
                    self.open_position(jp)
            else:
                self.open_position(jp)

    def send_tao_status(self):
        """Send hourly TAO mining status update via Telegram."""
        now = time.time()
        if now - self.stats.last_tao_update < TAO_UPDATE_INTERVAL:
            return

        self.stats.last_tao_update = now

        # Get TAO balance
        tao_info = get_tao_balance()
        balance = tao_info["balance"]

        # Get Vanta health
        vanta = get_vanta_health()

        # Build status message
        lines = [
            "<b>⛏ TAO MINER STATUS</b>",
            f"Subnet: SN8 (Vanta) | UID 255",
            f"Uptime: {self.stats.uptime_str()}",
            "",
            f"<b>Wallet:</b> {balance:.4f} TAO",
            "",
            f"<b>Vanta Miner:</b> {vanta['status']}",
            f"<b>Bridge:</b> {'synced' if self.active_positions else 'idle'}",
            "",
            f"<b>Positions:</b> {len(self.active_positions)} open",
        ]

        for pair, pos in self.active_positions.items():
            age_min = int((now - pos.timestamp) / 60)
            lines.append(f"  {pair} {pos.direction} {pos.leverage}x ({age_min}m)")

        lines.extend([
            "",
            f"<b>Lifetime Stats:</b>",
            f"  Orders: {self.stats.orders_sent} sent, {self.stats.orders_filled} filled",
            f"  Opened: {self.stats.positions_opened} | Closed: {self.stats.positions_closed}",
            f"  Flips: {self.stats.direction_flips}",
            f"  Portfolio leverage: {self.total_leverage:.2f}x",
            "",
            f"<i>Challenge: day {self._challenge_day()}/61-90</i>",
        ])

        msg = "\n".join(lines)
        tg_send(msg)
        log.info("Sent hourly TAO status update")

    def _challenge_day(self) -> int:
        """Estimate challenge day (trading days since registration)."""
        # Registered on 2026-03-12
        from datetime import date
        start = date(2026, 3, 12)
        today = date.today()
        delta = (today - start).days
        # Rough estimate: ~5/7 are trading days
        return max(1, int(delta * 5 / 7))

    def format_tao_status(self) -> str:
        """Format TAO status for Telegram /tao command (called from Jane)."""
        tao_info = get_tao_balance()
        vanta = get_vanta_health()
        now = time.time()

        lines = [
            "<b>⛏ TAO MINER</b>",
            f"SN8 Vanta | UID 255",
            f"Balance: <b>{tao_info['balance']:.4f} TAO</b>",
            f"Miner: {vanta['status']} | Bridge: {self.stats.uptime_str()}",
            "",
        ]

        if self.active_positions:
            lines.append(f"<b>Vanta Positions ({len(self.active_positions)}):</b>")
            for pair, pos in self.active_positions.items():
                age_min = int((now - pos.timestamp) / 60)
                lines.append(f"  {pair} {pos.direction} {pos.leverage}x ({age_min}m)")
        else:
            lines.append("No active Vanta positions")

        lines.extend([
            "",
            f"Orders: {self.stats.orders_sent} | Filled: {self.stats.orders_filled}",
            f"Opens: {self.stats.positions_opened} | Closes: {self.stats.positions_closed}",
            f"Challenge day: ~{self._challenge_day()}/61",
        ])

        return "\n".join(lines)

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
        log.info(f"Brackets:     {USE_BRACKET_ORDERS}")
        log.info(f"Poll interval: {POLL_INTERVAL}s")
        log.info(f"Telegram:     {'configured' if TELEGRAM_BOT_TOKEN else 'not configured'}")
        log.info("=" * 60)

        # Startup notification
        state = self.get_jane_state()
        if state:
            log.info(f"Jane connected | Bankroll: ${state.get('bankroll', 0):,.2f} | "
                     f"Open: {state.get('n_open', 0)} | Win rate: {state.get('win_rate', 0):.0%}")

        tg_send(
            "<b>⛏ TAO MINER ONLINE</b>\n"
            "SN8 Vanta | UID 255\n"
            f"Jane → Bridge → Vanta\n"
            f"BTC→BTCUSD, SOL→SOLUSD, AVAX→SOLUSD\n\n"
            f"<i>Type /tao for status updates</i>"
        )

        # Force first status update after 5 min
        self.stats.last_tao_update = time.time() - TAO_UPDATE_INTERVAL + 300

        cycle = 0
        while True:
            try:
                cycle += 1
                self.sync_positions()
                self.send_tao_status()

                if cycle % 10 == 0:
                    log.info(
                        f"Cycle {cycle} | Vanta positions: {len(self.active_positions)} | "
                        f"Portfolio leverage: {self.total_leverage:.2f}x"
                    )

            except KeyboardInterrupt:
                log.info("Shutting down bridge...")
                tg_send("<b>⛏ TAO MINER OFFLINE</b>\nBridge stopped.")
                break
            except Exception as e:
                log.error(f"Bridge error: {e}", exc_info=True)

            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    bridge = JaneVantaBridge()
    bridge.run()
