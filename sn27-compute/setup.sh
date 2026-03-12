#!/bin/bash
# SN27 Compute (Neural Internet) - Bare Metal GPU Compute Miner
# EASIEST: Straightforward GPU rental, installer script handles most setup
# Docs: https://github.com/neuralinternet/SN27
set -euo pipefail

echo "============================================"
echo " SN27 COMPUTE - Decentralized GPU Compute"
echo " Difficulty: EASIEST"
echo " Reward: GPU-score based (0.55 weight)"
echo "============================================"
echo ""

# Prerequisites
echo "[*] Checking prerequisites..."
MISSING=()
command -v docker &>/dev/null || MISSING+=("docker")
command -v btcli &>/dev/null || MISSING+=("bittensor (btcli)")
command -v nvidia-smi &>/dev/null || MISSING+=("nvidia-drivers")
command -v pm2 &>/dev/null || MISSING+=("pm2 (npm install -g pm2)")
command -v hashcat &>/dev/null || MISSING+=("hashcat")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "[!] Missing: ${MISSING[*]}"
    echo ""
fi

# Clone SN27
if [ ! -d "SN27" ]; then
    echo "[+] Cloning SN27 repo..."
    git clone https://github.com/neuralinternet/SN27.git
fi

echo ""
echo "=== SETUP STEPS ==="
echo ""
echo "1. HARDWARE:"
echo "   - Minimum GPU: RTX 4090 (lowest tier that scores)"
echo "   - Recommended: H100/H200 for top rewards"
echo "   - Ubuntu 22.04/24.04 bare metal ONLY"
echo "   - NOT supported: RunPod, VastAI, Lambda"
echo "   - Acceptable: Oracle, CoreWeave, Latitude.sh (dedicated)"
echo ""
echo "2. RUN INSTALLER:"
echo "   cd SN27"
echo "   bash scripts/installation_script/compute_subnet_installer.sh"
echo "   # Installs: CUDA 12.8, Docker, NVIDIA Container Toolkit, btcli, PM2"
echo ""
echo "3. CREATE WALLET & REGISTER:"
echo "   btcli wallet new_coldkey --wallet.name tao_miner"
echo "   btcli wallet new_hotkey --wallet.name tao_miner --wallet.hotkey default"
echo "   btcli subnet register --netuid 27 --wallet.name tao_miner --wallet.hotkey default"
echo ""
echo "4. INSTALL HASHCAT:"
echo "   sudo apt-get install -y hashcat"
echo "   # Required for Proof-of-Work challenges (BLAKE2b-512)"
echo ""
echo "5. OPEN FIREWALL PORTS:"
echo "   sudo ufw allow 4444/tcp   # Production SSH (allocations + PoG)"
echo "   sudo ufw allow 4445/tcp   # Test SSH (validator PoG testing)"
echo "   sudo ufw allow 8091/tcp   # Axon (Bittensor comms)"
echo "   sudo ufw allow 27015:27018/tcp  # Client external ports"
echo ""
echo "6. START MINER:"
echo "   cd SN27"
echo "   pm2 start neurons/miner.py --name sn27-miner --interpreter python3 -- \\"
echo "     --netuid 27 \\"
echo "     --subtensor.network finney \\"
echo "     --wallet.name tao_miner \\"
echo "     --wallet.hotkey default \\"
echo "     --axon.port 8091 \\"
echo "     --ssh.port 4444"
echo ""
echo "   pm2 save && pm2 startup"
echo ""
echo "=== SCORING ==="
echo "  Formula: base_gpu_score × num_gpus × 100"
echo "  GPU weight: 0.55 of total score"
echo "  +20% bonus if allocated to a client"
echo "  Up to 8 GPUs recognized per miner"
echo "  GPU scores loaded from remote config every 300s"
echo ""
echo "=== HOW IT WORKS ==="
echo "  1. Validators SSH into your miner container"
echo "  2. Run Proof-of-GPU: FP16/FP32 matrix multiplication benchmarks"
echo "  3. Merkle tree verification of results"
echo "  4. Hashcat PoW challenges (BLAKE2b-512, difficulty 7-12, 30s timeout)"
echo "  5. Score based on GPU performance × count"
echo "  6. Clients can SSH in to run their own workloads"
echo ""
echo "=== GPU TIERS (approximate scores) ==="
echo "  RTX 4090:  Entry level"
echo "  A6000:     Mid tier"
echo "  A100:      High tier"
echo "  H100:      Top tier"
echo "  H200:      Maximum rewards"
