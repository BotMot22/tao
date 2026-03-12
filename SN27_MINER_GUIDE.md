# Bittensor SN27 (Neural Internet Compute) - Complete Miner Deployment Guide

## 1. Architecture Overview

SN27 is a **decentralized GPU compute marketplace** on the Bittensor network. It operates as a verifiable distributed supercomputing platform where miners contribute GPU resources and earn TAO rewards based on verified hardware performance.

### Three Node Types

| Role | Purpose |
|------|---------|
| **Miners** | Provide GPU compute resources via Docker containers with SSH access |
| **Validators** | Benchmark miners via Proof-of-GPU (PoG), set weights on-chain |
| **API/Clients** | Request compute allocations through validators |

### Task Assignment Flow

1. Validators use **epoch-based scheduling** (tied to block numbers) to determine which validator tests which miner, preventing coordination attacks
2. Tasks alternate between **"legacy PoG"** for allocated miners and **"Sybil-resistant PoG"** for available miners
3. Validators SSH into miner containers to run benchmarks directly
4. GPU identification is done by matching measured TFLOPS against known GPU performance profiles

### Communication Protocols (Bittensor Synapses)

| Protocol | Purpose | Timeout |
|----------|---------|---------|
| **Specs** | Miners respond with JSON hardware details (CPU, GPU, RAM, disk) | 60s |
| **Allocate** | Resource provisioning with RSA encryption + SSH key exchange | - |
| **Challenge** | Hashcat-based proof-of-work using BLAKE2b-512 (mode 610) | 30s |

---

## 2. What Workloads Miners Actually Run

Miners do NOT run arbitrary AI training jobs. They run:

### A. Proof-of-GPU (PoG) Validation - Three Sequential Phases

1. **Benchmarking Mode**: Validators execute `miner_script.py` via SSH on the miner. The script performs FP16/FP32 matrix multiplication operations, measuring TFLOPS and VRAM
2. **Merkle Tree Generation**: Miners compute matrices and generate cryptographic root hashes for verification
3. **Challenge-Response**: Validators send random challenge indices; miners extract specific matrix elements and provide Merkle proofs. Hash integrity is verified via `compute_script_hash()` before execution

### B. Hashcat Proof-of-Work Challenges

- Mode: BLAKE2b-512 (hashcat mode 610)
- Difficulty: 7-12 characters from ~94-character set
- Miner runs hashcat with workload profile "3" (high performance) and `-O` optimization flag
- Must solve within 30-second timeout

### C. Resource Allocation (Actual Client Workloads)

When allocated to a client through a validator:
- Docker container with SSH access is provisioned
- Client gets SSH credentials (encrypted via RSA during allocation)
- Client runs their own workloads (AI training, inference, etc.)
- Miner gets a +20% score bonus while allocated

---

## 3. Hardware Requirements

### Minimum System Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Ubuntu 22.04 or 24.04 |
| **GPU** | NVIDIA with CUDA support (minimum RTX 4090 tier) |
| **CUDA** | 12.4+ (installer sets up 12.8) |
| **NVIDIA Drivers** | 525+ |
| **RAM** | Minimum 8GB (more recommended) |
| **Storage** | 50GB+ |
| **Python** | 3.10+ (target 3.12) |
| **Network** | Stable internet, static IP preferred |

### Supported GPU Tiers (Ranked by Score)

The scoring system is **dynamically loaded from a remote config server** every 300 seconds. As of the latest known configuration, supported GPUs from lowest to highest tier:

| GPU Model | Tier | Notes |
|-----------|------|-------|
| RTX 4090 | Entry | Minimum supported GPU |
| A100 40GB | Mid | Data center grade |
| A100 80GB | Mid-High | More VRAM, higher score |
| H100 | High | Recommended for top rewards |
| H200 | Premium | Highest current scores |
| B200 | Premium | Next-gen support |
| RTX 5090 | Supported | Consumer flagship |

**Scoring formula**: `base_gpu_score * num_gpus * 100` (max 8 GPUs recognized per miner, +20% if allocated)

**GPU weight in overall score**: 0.55 (highest). CPU: 0.20, RAM: 0.15, Disk: 0.10

### Important Hardware Notes

- **Container-based GPU platforms NOT supported**: RunPod, VastAI, Lambda are explicitly unsupported
- **In-house hardware strongly encouraged** for better control and rewards
- **Acceptable cloud providers**: Oracle, CoreWeave, Latitude.sh (bare metal only)
- **Each UID is limited to one external IP**

---

## 4. Scoring & Reward Mechanism

### Score Calculation (`calc_score_pog()`)

```
1. base_score = config_data["gpu_performance"][gpu_name]  # Lookup by GPU model
2. multi_gpu_score = base_score * num_gpus                 # Up to 8 GPUs
3. allocation_bonus = score * 1.20 if currently_allocated  # +20% bonus
4. final_score = calculated_score * 100
```

### Weight Distribution (`set_weight_capped_by_gpu()`)

- Groups miners by GPU type
- Each GPU group has a cap: `group_cap = (gpu_priority / total_priority) * total_miner_emission`
- Scores normalized within each group
- Remaining weight sent to burn address
- Rate limit: 100 blocks between weight updates

### Penalties

Miners are penalized (excluded from emission) for:
- Failed SSH connections (hardware unavailability)
- Script integrity failures (modified miner code)
- Timeout during proof-of-work (>30s)
- Merkle proof verification failures
- Being on the suspected exploiters blacklist (17 known addresses)

---

## 5. Step-by-Step Setup Process

### Step 1: System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install prerequisites
sudo apt install -y git curl build-essential software-properties-common

# Set up firewall
sudo ufw allow 22/tcp     # System SSH
sudo ufw allow 4444/tcp   # Miner allocation SSH (production)
sudo ufw allow 4445/tcp   # Test SSH (validator PoG testing)
sudo ufw allow 8091/tcp   # Axon port (Bittensor validator-miner communication)
sudo ufw allow 27015:27018/tcp  # External ports for client use
sudo ufw enable
```

### Step 2: Clone Repository and Run Installer

```bash
# Clone the repo (check current repo name - may be SN27 or compute-subnet)
git clone https://github.com/neuralinternet/SN27.git
cd SN27

# Run the automated installer
bash scripts/installation_script/compute_subnet_installer.sh
```

The installer handles:
- CUDA 12.8 installation (detects existing versions)
- Docker CE with NVIDIA Container Toolkit
- Bittensor CLI (btcli)
- Node.js and PM2 process manager
- Python dependencies
- Docker socket permissions via `setfacl`

### Step 3: Verify Installation

```bash
# Verify GPU
nvidia-smi

# Verify Docker
docker --version

# Verify CUDA
nvcc --version

# Verify Bittensor
btcli subnet list

# Test CUDA-Docker integration
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### Step 4: Set CUDA Environment Variables

Add to `~/.bashrc` if not already set by installer:

```bash
export PATH=/usr/local/cuda-12.8/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH
source ~/.bashrc
```

### Step 5: Create Wallet

```bash
# Create new coldkey (stores TAO, keep secure)
btcli wallet new_coldkey --wallet.name miner_wallet

# Create new hotkey (used for mining)
btcli wallet new_hotkey --wallet.name miner_wallet --wallet.hotkey miner_hotkey

# OR import existing wallet
btcli wallet import_seed --wallet.name miner_wallet
```

Wallets are stored in `~/.bittensor/wallets/`

### Step 6: Fund Wallet and Register

You need TAO in your coldkey to register.

```bash
# Register on mainnet (netuid 27)
btcli subnet register --netuid 27 --wallet.name miner_wallet --wallet.hotkey miner_hotkey

# OR register on testnet (netuid 15) for testing
btcli subnet register --netuid 15 --wallet.name miner_wallet --wallet.hotkey miner_hotkey --subtensor.network test
```

### Step 7: Install Hashcat

```bash
sudo apt install -y hashcat

# Verify
hashcat --version
```

### Step 8: Install Python Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies:
- `bittensor==9.0.0`
- `bittensor-cli==9.1.0`
- `bittensor-wallet==3.0.4`
- `docker==7.0.0`
- `paramiko==3.4.1`
- `nvidia-ml-py==12.570.86`
- `wandb` (for cross-validator coordination)
- PyTorch ecosystem

### Step 9: Start the Miner with PM2

```bash
# Install PM2 globally
npm install -g pm2

# Start miner on mainnet
pm2 start neurons/miner.py --name sn27-miner --interpreter python3 -- \
  --netuid 27 \
  --subtensor.network finney \
  --subtensor.chain_endpoint subvortex.info:9944 \
  --wallet.name miner_wallet \
  --wallet.hotkey miner_hotkey \
  --axon.port 8091 \
  --ssh.port 4444 \
  --miner.hashcat.path hashcat \
  --miner.hashcat.workload.profile 3 \
  --miner.hashcat.extended.options "-O" \
  --logging.debug

# Save PM2 config for auto-restart
pm2 save
pm2 startup
```

### Step 10: Verify Miner is Running

```bash
# Check PM2 status
pm2 status

# Check logs
pm2 logs sn27-miner

# Verify axon is accessible
# Your miner should appear in the metagraph
```

---

## 6. Docker/Container Setup

Docker is used to isolate allocated compute resources, NOT to run the miner itself.

### How Docker Works in SN27

1. When a validator allocates resources to your miner, it creates a Docker container
2. The container runs an SSH server (port 4444 by default)
3. Validators SSH into this container to run PoG benchmarks
4. Clients SSH into allocated containers for their workloads

### Docker Configuration (from Allocate Protocol)

```json
{
  "docker_requirement": {
    "base_image": "ubuntu",
    "ssh_key": "<validator_public_key>",
    "ssh_port": 4444,
    "volume_path": "/tmp",
    "dockerfile": null
  }
}
```

### Container Lifecycle Management

The miner exposes API endpoints for container control:
- `/service/restart_docker` - Stop and restart (preserves volumes)
- `/service/pause_docker` - Suspend execution
- `/service/unpause_docker` - Resume execution
- `/service/exchange_docker_key` - Rotate SSH credentials

### Ensure Docker GPU Access

```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
  && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Test GPU in container
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

---

## 7. Configuration Files

### Environment File (.env)

Created by the installer, stores PM2 launch parameters:

```env
HOME_DIR=/home/ubuntu
WALLET_NAME=miner_wallet
HOTKEY_NAME=miner_hotkey
NETUID=27
SUBTENSOR_NETWORK=finney
SUBTENSOR_ENDPOINT=subvortex.info:9944
AXON_PORT=8091
SSH_PORT=4444
```

### Key Config Parameters (compute/__init__.py)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `__version__` | 2.0.0 | Current version |
| `validator_permit_stake` | 10,000 TAO | Min validator stake |
| `pog_retry_limit` | 30 | Max PoG retry attempts |
| `pog_retry_interval` | 80s | Time between retries |
| `pow_timeout` | 30s | Hashcat challenge timeout |
| `pow_min_difficulty` | 7 | Min challenge chars |
| `pow_max_difficulty` | 12 | Max challenge chars |
| `pow_default_mode` | 610 | BLAKE2b-512 hashcat mode |
| `miner_hashcat_workload_profile` | 3 | High performance |
| `specs_timeout` | 60s | Hardware query timeout |
| `weights_rate_limit` | 100 blocks | Between weight updates |

### SQLite Database (ComputeDb)

Automatically managed. Tables:
- `miner_details` - Hardware specifications
- `pog_stats` - GPU performance history
- `challenge_details` - PoW results with success rates
- `allocation` - Active resource allocations
- `stats` - Current scores and reliability metrics
- `blacklist` - Penalized miners

---

## 8. Port Configuration Summary

| Port | Protocol | Purpose | Required |
|------|----------|---------|----------|
| 4444 | TCP | Production SSH (allocations + PoG) | YES |
| 4445 | TCP | Test SSH (validator PoG testing) | YES |
| 8091 | TCP | Axon (Bittensor validator-miner comms) | YES |
| 27015-27018 | TCP | External ports for client use | Recommended |

---

## 9. CLI Arguments Reference (Miner)

| Argument | Default | Purpose |
|----------|---------|---------|
| `--netuid` | - | 27 (mainnet) or 15 (testnet) |
| `--subtensor.network` | - | `finney` for mainnet, `test` for testnet |
| `--subtensor.chain_endpoint` | - | `subvortex.info:9944` |
| `--wallet.name` | - | Coldkey wallet name |
| `--wallet.hotkey` | - | Hotkey name |
| `--axon.port` | 8091 | Bittensor communication port |
| `--ssh.port` | 4444 | SSH allocation port |
| `--miner.hashcat.path` | `hashcat` | Path to hashcat binary |
| `--miner.hashcat.workload.profile` | `3` | Hashcat workload (1-4) |
| `--miner.hashcat.extended.options` | `""` | Extra hashcat flags |
| `--miner.whitelist.not.enough.stake` | False | Allow low-stake validators |
| `--miner.whitelist.not.updated` | False | Allow outdated validators |
| `--miner.whitelist.updated.threshold` | 60 | Quorum threshold |
| `--auto_update` | - | Enable auto-updates |
| `--logging.debug` | - | Debug logging |
| `--blacklist.hotkeys` | - | Blacklisted hotkeys |

---

## 10. Monitoring & Maintenance

### PM2 Commands

```bash
pm2 status              # Check miner status
pm2 logs sn27-miner     # View logs
pm2 restart sn27-miner  # Restart miner
pm2 stop sn27-miner     # Stop miner
pm2 monit               # Real-time monitoring
```

### Health Checks

```bash
# GPU monitoring
nvidia-smi -l 1

# Docker containers
docker ps -a

# Network connectivity
btcli subnet list --netuid 27

# Check your miner's registration
btcli wallet overview --wallet.name miner_wallet
```

### WandB Integration

The system uses Weights & Biases for cross-validator coordination:
- Shared allocation state
- Performance statistics
- System metrics

---

## 11. Security Notes

- 12 trusted validator hotkeys are whitelisted (Opentensor Foundation, Foundry, Neural Internet, etc.)
- 17 suspected exploiter hotkeys are blacklisted
- RSA encryption protects SSH credential exchange during allocation
- Script hash verification (`compute_script_hash()`) ensures miner code integrity
- SSH key rotation supported without container restart

---

## 12. Quick Reference - Full Deployment Checklist

```
[ ] Ubuntu 22.04/24.04 bare metal or dedicated server
[ ] NVIDIA GPU (RTX 4090 minimum, H100/H200 recommended)
[ ] Static IP address
[ ] Open ports: 4444, 4445, 8091, 27015-27018
[ ] Run compute_subnet_installer.sh
[ ] Verify: nvidia-smi, docker, nvcc, btcli
[ ] Create wallet (coldkey + hotkey)
[ ] Fund coldkey with TAO
[ ] Register on netuid 27
[ ] Install hashcat
[ ] pip install -r requirements.txt
[ ] Start miner via PM2
[ ] Verify logs and metagraph presence
[ ] Monitor with pm2 monit + nvidia-smi
```

---

## Sources

- https://github.com/neuralinternet/SN27 (main repo)
- https://deepwiki.com/neuralinternet/SN27 (architecture analysis)
- https://docs.neuralinternet.ai/ (official docs)
- https://neuralinternet.ai/blog/mining (setup guide)
- https://medium.com/@neuralinternet/how-to-run-a-compute-miner-82498b93e7e1
- https://docs.neuralinternet.ai/miner-system/ni_compue_subnet_miner_setup/
- https://docs.neuralinternet.ai/ni-ecosystem/ni-compute-sn27/ai-gpu-benchmarking-with-proof-of-gpu
