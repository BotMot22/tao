#!/bin/bash
# SN64 Chutes Miner - Bootstrap Setup
# HARDEST: Requires Kubernetes, Ansible, GPU fleet, Helm charts
# Docs: https://chutes.ai/docs/miner-resources/overview
set -euo pipefail

echo "============================================"
echo " SN64 CHUTES - Serverless GPU Inference"
echo " Difficulty: HARD"
echo " Reward: Highest emissions (~14% of network)"
echo "============================================"
echo ""

# Prerequisites check
echo "[*] Checking prerequisites..."
MISSING=()
command -v ansible &>/dev/null || MISSING+=("ansible")
command -v kubectl &>/dev/null || MISSING+=("kubectl")
command -v helm &>/dev/null || MISSING+=("helm")
command -v btcli &>/dev/null || MISSING+=("bittensor (btcli)")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "[!] Missing tools: ${MISSING[*]}"
    echo ""
    echo "Install them:"
    echo "  pip install ansible bittensor"
    echo "  curl -sfL https://get.k3s.io | sh -"
    echo "  curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
    echo ""
fi

# Clone miner repo
if [ ! -d "chutes-miner" ]; then
    echo "[+] Cloning chutes-miner repo..."
    git clone https://github.com/chutesai/chutes-miner.git
fi

echo ""
echo "=== SETUP STEPS ==="
echo ""
echo "1. HARDWARE NEEDED:"
echo "   - 1x CPU control node (4-8 cores, 32-64GB RAM)"
echo "   - 1+ GPU worker nodes (bare metal/VM only, NOT Runpod/Vast)"
echo "   - Supported GPUs: RTX 3090/4090/5090, A10, A40, A100, H100, H200, B200"
echo "   - RAM must be >= total VRAM across all GPUs"
echo "   - 850GB+ storage per GPU node for model cache"
echo "   - Static public IPs with 1:1 port mapping"
echo ""
echo "2. CONFIGURE ANSIBLE:"
echo "   cp inventory.yml chutes-miner/ansible/k3s/inventory.yml"
echo "   # Edit with your node IPs, SSH keys, wallet paths"
echo ""
echo "3. CONFIGURE HELM:"
echo "   cp values.yaml chutes-miner/values.yaml"
echo "   # Edit with your validator config, cache settings"
echo ""
echo "4. DEPLOY GEPETTO STRATEGY:"
echo "   cp gepetto.py chutes-miner/gepetto.py"
echo "   # This is your competitive edge - customize deployment logic"
echo ""
echo "5. PROVISION CLUSTER:"
echo "   cd chutes-miner/ansible/k3s"
echo "   ansible-playbook playbooks/site.yml -i inventory.yml"
echo ""
echo "6. DEPLOY HELM CHARTS:"
echo "   cd chutes-miner"
echo "   kubectl create namespace chutes"
echo "   # Create secrets (see values.yaml comments)"
echo "   helm template . --set createPasswords=true -s templates/one-time-passwords.yaml | kubectl apply -n chutes -f -"
echo "   helm template . -f values.yaml > miner-charts.yaml"
echo "   kubectl apply -f miner-charts.yaml -n chutes"
echo ""
echo "7. REGISTER:"
echo "   btcli subnet register --netuid 64 --wallet.name tao_miner --wallet.hotkey default"
echo "   # Do NOT announce an axon - comms are via client-side socket.io"
echo ""
echo "8. ADD GPU NODES:"
echo "   pip install chutes-miner-cli"
echo "   chutes-miner add-node --name <hostname> --validator <vali_hotkey> \\"
echo "     --hourly-cost 0.50 --gpu-short-ref a100_80g_sxm \\"
echo "     --hotkey ~/.bittensor/wallets/tao_miner/hotkeys/default \\"
echo "     --miner-api http://<CPU_NODE_IP>:32000"
echo ""
echo "=== SCORING (7-day rolling window) ==="
echo "  55% Compute Units (bounties + compute time)"
echo "  25% Invocation Count (successful inference jobs)"
echo "  15% Unique Chute Score (diversity of models served)"
echo "   5% Bounty Count (first-to-deploy bonuses)"
echo ""
echo "=== WARNINGS ==="
echo "  - Single UID only (multiple UIDs = self-competition)"
echo "  - Takes 7 days for weights to stabilize"
echo "  - Gepetto strategy is everything - optimize it"
echo "  - GraVal validates GPU authenticity (no faking)"
