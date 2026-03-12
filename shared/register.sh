#!/bin/bash
# Register on a Bittensor subnet
set -euo pipefail

WALLET_NAME="${1:?Usage: register.sh <wallet> <hotkey> <netuid>}"
HOTKEY_NAME="${2:?Usage: register.sh <wallet> <hotkey> <netuid>}"
NETUID="${3:?Usage: register.sh <wallet> <hotkey> <netuid>}"
NETWORK="${4:-finney}"  # finney (mainnet) or test

echo "=== Subnet Registration ==="
echo "Wallet: $WALLET_NAME | Hotkey: $HOTKEY_NAME | Subnet: $NETUID | Network: $NETWORK"
echo ""

# Check balance first
echo "[*] Checking wallet balance..."
btcli wallet balance --wallet.name "$WALLET_NAME" --subtensor.network "$NETWORK" 2>/dev/null || true
echo ""

# Register
echo "[+] Registering on subnet $NETUID..."
btcli subnet register \
    --wallet.name "$WALLET_NAME" \
    --wallet.hotkey "$HOTKEY_NAME" \
    --netuid "$NETUID" \
    --subtensor.network "$NETWORK"

echo ""
echo "=== Registered ==="
echo "You are now registered on subnet $NETUID"
echo ""
echo "Subnet targets:"
echo "  SN64 (Chutes)       -> cd sn64-chutes && bash setup.sh"
echo "  SN12 (ComputeHorde) -> cd sn12-computehorde && bash setup.sh"
echo "  SN8  (Vanta/Taoshi) -> cd sn08-vanta && bash setup.sh"
echo "  SN27 (Compute)      -> cd sn27-compute && bash setup.sh"
