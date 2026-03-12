#!/bin/bash
# SN8 Vanta × Jane Bridge - Complete Setup
# Pipes Jane's 26-factor alpha signals into Vanta for TAO rewards
set -euo pipefail

echo "============================================"
echo " SN8 VANTA × JANE QUANT BRIDGE"
echo " Jane (8080) → Bridge → Vanta (8088)"
echo "============================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- 1. Prerequisites ---
echo "[*] Checking prerequisites..."
MISSING=()
command -v python3 &>/dev/null || MISSING+=("python3")
command -v btcli &>/dev/null || MISSING+=("bittensor (btcli)")
command -v pm2 &>/dev/null || MISSING+=("pm2")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "[!] Missing: ${MISSING[*]}"
    echo "  pip install bittensor requests"
    echo "  npm install -g pm2"
    exit 1
fi

# --- 2. Clone & install Vanta ---
if [ ! -d "vanta-network" ]; then
    echo "[+] Cloning vanta-network..."
    git clone https://github.com/taoshidev/vanta-network.git
    cd vanta-network
    python3 -m venv venv
    . venv/bin/activate
    export PIP_NO_CACHE_DIR=1
    pip install -r requirements.txt
    python3 -m pip install -e .
    pip install git+https://github.com/taoshidev/vanta-cli.git
    cd "$SCRIPT_DIR"
else
    echo "[*] vanta-network already cloned"
fi

# --- 3. Setup API keys ---
if [ ! -f "vanta-network/vanta_api/api_keys.json" ]; then
    echo "[+] Creating API keys..."
    mkdir -p vanta-network/vanta_api
    cp api_keys.json vanta-network/vanta_api/api_keys.json
    echo "[!] EDIT vanta-network/vanta_api/api_keys.json with a secure key"
    echo "[!] ALSO update VANTA_API_KEY in strategy.py to match"
fi

# --- 4. Install bridge dependencies ---
echo "[+] Installing bridge dependencies..."
pip install requests >/dev/null 2>&1

# --- 5. Verify Jane is running ---
echo ""
echo "[*] Checking Jane quant agent..."
if curl -s http://127.0.0.1:8080/api/state >/dev/null 2>&1; then
    JANE_STATE=$(curl -s http://127.0.0.1:8080/api/state)
    echo "[✓] Jane is running"
    echo "    Bankroll: $(echo "$JANE_STATE" | python3 -c "import sys,json; print(f'\${json.load(sys.stdin).get(\"bankroll\",0):,.2f}')" 2>/dev/null || echo "unknown")"
    echo "    Open positions: $(echo "$JANE_STATE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('n_open',0))" 2>/dev/null || echo "unknown")"
else
    echo "[!] Jane not running at http://127.0.0.1:8080"
    echo "    Start Jane first: cd /root/jane && python jane.py"
    echo "    The bridge will retry automatically once started"
fi

echo ""
echo "=== DEPLOYMENT STEPS ==="
echo ""
echo "1. REGISTER on SN8 (if not already):"
echo "   btcli subnet register --netuid 8 --wallet.name tao_miner --wallet.hotkey default"
echo ""
echo "2. SELECT ASSET CLASS (one-time, permanent):"
echo "   cd vanta-network && source venv/bin/activate"
echo "   vanta asset select  # Choose: crypto"
echo ""
echo "3. DEPOSIT COLLATERAL:"
echo "   vanta collateral deposit  # Minimum: 300 THETA"
echo ""
echo "4. START VANTA MINER:"
echo "   cd vanta-network && source venv/bin/activate"
echo "   pm2 start neurons/miner.py --name vanta-miner --interpreter python3 -- \\"
echo "     --netuid 8 --wallet.name tao_miner --wallet.hotkey default"
echo ""
echo "5. START JANE→VANTA BRIDGE:"
echo "   pm2 start $SCRIPT_DIR/strategy.py --name jane-vanta-bridge --interpreter python3"
echo ""
echo "6. MONITOR:"
echo "   pm2 logs jane-vanta-bridge"
echo "   tail -f $SCRIPT_DIR/bridge.log"
echo "   # Vanta dashboard: https://dashboard.taoshi.io"
echo ""
echo "=== SIGNAL FLOW ==="
echo "  Jane (26 factors) → alpha score + direction"
echo "    → Bridge polls every 30s"
echo "    → Filters: score >= 0.50, confidence >= 0.50"
echo "    → Maps: BTC→BTCUSD, SOL→SOLUSD"
echo "    → Sizes: leverage = 0.1 + (strength × 0.4), max 0.5x"
echo "    → Bracket orders with Jane's SL/TP levels"
echo "    → Vanta miner receives signal on port 8088"
echo ""
echo "=== RISK CONTROLS ==="
echo "  Max leverage/trade:  0.5x (Vanta limit: 2.5x)"
echo "  Max portfolio:       1.5x (Vanta limit: 5x)"
echo "  Bracket orders:      SL/TP from Jane's ATR/VaR calculations"
echo "  Drawdown protection: Vanta eliminates at 10%, we stay under 5%"
