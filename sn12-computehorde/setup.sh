#!/bin/bash
# SN12 ComputeHorde Miner - Bootstrap Setup
# MEDIUM-HARD: Requires A6000 GPU, Docker, SSH access
# Docs: https://github.com/backend-developers-ltd/ComputeHorde
set -euo pipefail

echo "============================================"
echo " SN12 COMPUTEHORDE - GPU Compute Rental"
echo " Difficulty: MEDIUM-HARD"
echo " Reward: Mid-high emissions"
echo "============================================"
echo ""

# Prerequisites
echo "[*] Checking prerequisites..."
MISSING=()
command -v docker &>/dev/null || MISSING+=("docker")
command -v btcli &>/dev/null || MISSING+=("bittensor (btcli)")
command -v nvidia-smi &>/dev/null || MISSING+=("nvidia-drivers")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "[!] Missing: ${MISSING[*]}"
    echo ""
    echo "Install Docker:"
    echo "  curl -fsSL https://get.docker.com | sh"
    echo "  sudo usermod -aG docker \$USER"
    echo ""
    echo "Install NVIDIA Container Toolkit:"
    echo "  distribution=\$(. /etc/os-release;echo \$ID\$VERSION_ID)"
    echo "  curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -"
    echo "  sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit"
    echo "  sudo nvidia-ctk runtime configure --runtime=docker"
    echo "  sudo systemctl restart docker"
    echo ""
fi

echo ""
echo "=== SETUP STEPS ==="
echo ""
echo "1. HARDWARE NEEDED:"
echo "   - NVIDIA A6000 GPU (only supported GPU currently, A100 coming)"
echo "   - 500GB+ SSD"
echo "   - Ubuntu 22.04/24.04"
echo "   - Bare metal or dedicated server (NOT Runpod/Vast)"
echo "   - SSH access from your local machine"
echo ""
echo "2. CONFIGURE:"
echo "   cp config.env .env"
echo "   # Edit .env with your wallet details"
echo ""
echo "3. REGISTER ON SUBNET:"
echo "   btcli subnet register --netuid 12 --wallet.name tao_miner --wallet.hotkey default"
echo ""
echo "4. INSTALL MINER (one-liner from local machine):"
echo "   curl -sSfL https://github.com/backend-developers-ltd/ComputeHorde/raw/master/install_miner.sh | \\"
echo "     bash -s - production <SSH_USER@GPU_SERVER_IP> ~/.bittensor/wallets/tao_miner/hotkeys/default"
echo ""
echo "   This installs: Docker, CUDA, docker-compose, postgres, redis, nginx, app, worker, pylon, watchtower"
echo ""
echo "5. DEPOSIT COLLATERAL (for organic job eligibility):"
echo "   Minimum: 0.01 TAO per validator (increasing to 10 TAO)"
echo "   See: https://github.com/bactensor/collateral-contracts"
echo ""
echo "=== SCORING ==="
echo "  - Executor-seconds: proportional to GPU count × validator stake"
echo "  - 10 testing cycles per day (722 blocks each)"
echo "  - 1 point per synthetic job + 1 point per organic job"
echo "  - 10% 'dancing bonus' for rotating hotkeys between cycles"
echo "  - 20% penalty if below 10% peak executors outside peak"
echo ""
echo "=== STRATEGY ==="
echo "  - Stock single-executor is NOT competitive"
echo "  - Build custom executor manager for multiple GPU instances"
echo "  - Preload Docker images via cron for faster job starts"
echo "  - Deposit collateral with top validators for organic jobs"
echo "  - Declare full capacity during peak testing cycles"
echo "  - Test on testnet (netuid 174) first"
