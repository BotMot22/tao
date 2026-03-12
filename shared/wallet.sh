#!/bin/bash
# Bittensor wallet creation helper
set -euo pipefail

WALLET_NAME="${1:-tao_miner}"
HOTKEY_NAME="${2:-default}"

echo "=== Bittensor Wallet Setup ==="
echo "Wallet: $WALLET_NAME | Hotkey: $HOTKEY_NAME"
echo ""

# Install bittensor if missing
if ! command -v btcli &>/dev/null; then
    echo "[+] Installing bittensor..."
    pip install bittensor
fi

# Create coldkey
if [ ! -d "$HOME/.bittensor/wallets/$WALLET_NAME" ]; then
    echo "[+] Creating coldkey: $WALLET_NAME"
    btcli wallet new_coldkey --wallet.name "$WALLET_NAME"
    echo ""
    echo "!!! SAVE YOUR MNEMONIC SECURELY !!!"
    echo ""
else
    echo "[*] Coldkey '$WALLET_NAME' already exists"
fi

# Create hotkey
if [ ! -f "$HOME/.bittensor/wallets/$WALLET_NAME/hotkeys/$HOTKEY_NAME" ]; then
    echo "[+] Creating hotkey: $HOTKEY_NAME"
    btcli wallet new_hotkey --wallet.name "$WALLET_NAME" --wallet.hotkey "$HOTKEY_NAME"
else
    echo "[*] Hotkey '$HOTKEY_NAME' already exists"
fi

echo ""
echo "=== Wallet Ready ==="
btcli wallet overview --wallet.name "$WALLET_NAME" 2>/dev/null || true
echo ""
echo "Next: Fund your coldkey with TAO, then register on a subnet:"
echo "  bash shared/register.sh $WALLET_NAME $HOTKEY_NAME <NETUID>"
