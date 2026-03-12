#!/bin/bash
# Cross-subnet miner monitoring
set -euo pipefail

WALLET_NAME="${1:-tao_miner}"
NETWORK="${2:-finney}"

echo "=== TAO Miner Monitor ==="
echo "Wallet: $WALLET_NAME | Network: $NETWORK"
echo "Time: $(date -u '+%Y-%m-%d %H:%M UTC')"
echo ""

# Wallet balance
echo "--- Balance ---"
btcli wallet balance --wallet.name "$WALLET_NAME" --subtensor.network "$NETWORK" 2>/dev/null || echo "Could not fetch balance"
echo ""

# Check each subnet we care about
for NETUID in 64 12 8 27; do
    echo "--- Subnet $NETUID ---"
    btcli subnet metagraph --netuid "$NETUID" --subtensor.network "$NETWORK" 2>/dev/null | head -5 || echo "Not registered on SN$NETUID"
    echo ""
done

echo "--- External Dashboards ---"
echo "Taostats:     https://taostats.io/subnets"
echo "Vanta:        https://dashboard.taoshi.io"
echo "ComputeHorde: https://computehorde.io"
echo "Chutes:       https://chutes.ai"
