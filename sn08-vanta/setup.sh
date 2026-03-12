#!/bin/bash
# SN8 Vanta (Taoshi) - Futures Trading Signal Miner
# MEDIUM: CPU-only, but requires profitable trading strategy
# Docs: https://docs.taoshi.io/ptn/overview/
set -euo pipefail

echo "============================================"
echo " SN8 VANTA (TAOSHI) - Futures Trading"
echo " Difficulty: MEDIUM (strategy-dependent)"
echo " Reward: PnL-based (100% Avg Daily PnL)"
echo "============================================"
echo ""

# Prerequisites
echo "[*] Checking prerequisites..."
MISSING=()
command -v python3 &>/dev/null || MISSING+=("python3")
command -v btcli &>/dev/null || MISSING+=("bittensor (btcli)")
command -v pm2 &>/dev/null || MISSING+=("pm2")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "[!] Missing: ${MISSING[*]}"
    echo "  pip install bittensor"
    echo "  npm install -g pm2"
    echo ""
fi

# Clone vanta network
if [ ! -d "vanta-network" ]; then
    echo "[+] Cloning vanta-network..."
    git clone https://github.com/taoshidev/vanta-network.git
    cd vanta-network
    python3 -m venv venv
    . venv/bin/activate
    export PIP_NO_CACHE_DIR=1
    pip install -r requirements.txt
    python3 -m pip install -e .
    cd ..
else
    echo "[*] vanta-network already cloned"
fi

# Setup API keys
if [ ! -f "vanta-network/vanta_api/api_keys.json" ]; then
    echo "[+] Creating API keys file..."
    mkdir -p vanta-network/vanta_api
    cp api_keys.json vanta-network/vanta_api/api_keys.json
fi

echo ""
echo "=== SETUP STEPS ==="
echo ""
echo "1. HARDWARE: 2 vCPU + 8GB RAM (CPU only, no GPU needed)"
echo "   Any VPS works. Python 3.10 required."
echo ""
echo "2. REGISTER:"
echo "   btcli subnet register --netuid 8 --wallet.name tao_miner --wallet.hotkey default"
echo ""
echo "3. SELECT ASSET CLASS (permanent, cannot change):"
echo "   pip install git+https://github.com/taoshidev/vanta-cli.git"
echo "   vanta asset select"
echo "   Options: crypto | forex | commodities | equities"
echo ""
echo "4. DEPOSIT COLLATERAL:"
echo "   vanta collateral deposit"
echo "   Minimum: 300 THETA (\$150K trading capacity)"
echo "   Maximum: 1000 THETA (\$500K trading capacity)"
echo ""
echo "5. START MINER:"
echo "   cd vanta-network"
echo "   python neurons/miner.py --netuid 8 --wallet.name tao_miner --wallet.hotkey default"
echo "   # REST API starts on port 8088"
echo ""
echo "6. SEND TRADING SIGNALS:"
echo "   python strategy.py  # Our custom strategy"
echo "   # Or: POST http://127.0.0.1:8088/api/submit-order"
echo ""
echo "=== ASSET CLASSES ==="
echo "  Crypto:      BTCUSD, ETHUSD, SOLUSD, XRPUSD, DOGEUSD, ADAUSD"
echo "  Forex:       21 pairs (EURUSD, GBPUSD, etc.)"
echo "  Commodities: XAUUSD (Gold), XAGUSD (Silver)"
echo "  Equities:    25 stocks + 22 sector ETFs"
echo ""
echo "=== SCORING ==="
echo "  100% Average Daily PnL (USD change per trading day)"
echo "  Recency weighted: first 10 days = 40% of score"
echo "  Weekly payout cycle (targets Sunday midnight)"
echo ""
echo "=== ELIMINATION RULES ==="
echo "  - Max drawdown > 10% = PERMANENT elimination"
echo "  - Plagiarism (copying trades) = PERMANENT elimination"
echo "  - Challenge period: 61-90 trading days for new miners"
echo "  - Never reuse eliminated hotkeys"
echo ""
echo "=== LEVERAGE LIMITS ==="
echo "  Crypto:      0.01x-2.5x per position, 5x portfolio"
echo "  Forex:       0.1x-10x per position, 20x portfolio"
echo "  Commodities: 0.1x-4x per position"
echo "  Equities:    0.1x-2x per position, 2x portfolio"
