# ComputeHorde (Bittensor SN12) — Miner Deployment Guide

## 1. What Is ComputeHorde

ComputeHorde is Bittensor Subnet 12, designed to turn untrusted GPUs from miners into trusted compute resources. Validators from other subnets can access decentralized GPU power cost-effectively through the ComputeHorde SDK, replacing centralized cloud services.

- **Mainnet**: Subnet 12 (netuid 12)
- **Testnet**: Subnet 174
- **Repo**: https://github.com/backend-developers-ltd/ComputeHorde
- **Website**: https://computehorde.io
- **Discord**: #µ·horde·12 in Bittensor server

---

## 2. Architecture (5 Components)

### 2.1 Facilitator
- Gateway for organic requests from other subnets' validators
- Routes tasks to ComputeHorde validators who distribute them to miners

### 2.2 Validator
- Receives organic job requests via the Facilitator
- Distributes tasks to miners, evaluates results
- Runs a **Trusted Miner** (unregistered GPU) to pre-run validation tasks and establish expected outcomes
- Integrates with collateral smart contracts to filter miners and enable slashing
- Uses commit-reveal to prevent weight-copying

### 2.3 Miner
- Accepts job requests from validators
- Manages executors (GPU instances) that perform actual compute
- Returns results to validators for scoring
- Can deposit collateral to access paid organic jobs
- **Do NOT modify miner code** — competitive edge is in custom executor management

### 2.4 Executor
- Individual dockerized task instance spawned by a miner
- Operates in restricted environment with limited network access
- Assigned to hardware classes (currently A6000, A100 coming)
- Requires **minimum 500GB** shared disk space for Docker images and job data in `/tmp`
- Each miner can spawn **multiple executors** — removes the 256 UID limit

### 2.5 ComputeHorde SDK
- Python library for subnet owners/validators to submit jobs
- Supports cross-validation and fallback to cloud providers (RunPod via SkyPilot)

### Flow
```
Other Subnet Validator → Facilitator → CH Validator → Miner → Executor(s)
                                                          ↑
                                                    Trusted Miner (cross-validation)
```

---

## 3. Hardware Requirements

### Miner Machine (GPU Server)
| Component | Requirement |
|-----------|------------|
| **GPU** | NVIDIA A6000 (48GB VRAM) — only currently supported class |
| **Disk** | 500GB+ SSD (for Docker images + job data in /tmp) |
| **OS** | Ubuntu (only tested platform) |
| **Runtime** | Docker, Docker Compose, NVIDIA drivers, NVIDIA Container Toolkit |
| **Network** | Port 8000 open (configurable), SSH access |

A100 support is planned next. Long-term goal is all GPU types.

### Why A6000
- Synthetic validation tasks are designed to run ONLY on A6000 hardware
- This ensures miners deliver advertised compute power
- Hardware-specific tasks prevent spoofing

### Scaling
- Multiple A6000 GPUs per machine = multiple executors
- Multiple machines behind one miner UID via custom executor manager
- No upper limit on executors per miner

---

## 4. Scoring & Rewards System

### 4.1 Executor-Seconds (Allowance)
- Each block mints **executor-seconds** per miner-validator pair
- Total supply is proportional to number of executors (GPUs) in the subnet
- Each validator's share scales with their stake
- Starting a job consumes allowance equal to its runtime
- If a miner reduces executor count, tied allowance blocks become invalid

### 4.2 Testing Days & Peak Cycles
- ComputeHorde operates in **10-cycle testing days**
- Each cycle = 2 Bittensor tempos = 722 blocks
- **One cycle per day is the peak cycle**
- Scoring is primarily during peak cycles
- Miners should declare full executor capacity during peak cycles to maximize score
- Must maintain **at least 10% of peak executors** outside peak or face **20% penalty**

### 4.3 Scoring Formula
- **1 point** per successfully completed synthetic job
- **1 point** per successfully completed organic job (awarded in ALL cycles, not just peak)
- Scores are folded by coldkey, then split across hotkeys
- Hardware class weights adjust final incentives

### 4.4 Dancing Bonus (Executor Shuffling)
- Validators split each coldkey's score across its hotkeys
- The declared **main hotkey** takes the largest share in that cycle
- **Changing the main hotkey from the previous cycle triggers a 10% boost** on the coldkey before splitting
- Encourages miners to move GPUs across multiple UIDs
- Reduces effectiveness of weight-copying attacks

### 4.5 Anti-Gaming Measures
- **Commit-Reveal**: Validators post hidden weights, reveal next epoch
- **Executor Dancing**: Random GPU movement across UIDs
- **Selective Service Penalty**: Penalizes miners serving only subset of validators
- **Liquid Alpha**: Combats weight copying via vtrust mechanisms

### 4.6 Organic Jobs & Collateral
- Validators can require miners to deposit collateral (TAO) for paid organic jobs
- Dishonest miners face on-chain slashing
- Creates economic security — miners have skin in the game

---

## 5. Step-by-Step Miner Setup

### 5.1 Prerequisites
```bash
# You need:
# 1. A server with NVIDIA A6000 GPU(s), Ubuntu, SSH access
# 2. A local machine with your Bittensor wallet
# 3. btcli installed locally

pip install bittensor
```

### 5.2 Create Wallet (if not existing)
```bash
btcli wallet create --wallet.name miner
# This creates coldkey + hotkey under ~/.bittensor/wallets/miner/
```

### 5.3 Register on Subnet 12
```bash
# Mainnet
btcli subnet register --netuid 12 --wallet.name miner --wallet.hotkey default

# Testnet (for testing first)
btcli subnet register --netuid 174 --wallet.name miner --wallet.hotkey default --subtensor.network test
```

### 5.4 Run the Install Script
Execute from your **local machine** (where wallet files reside):

```bash
curl -sSfL https://github.com/backend-developers-ltd/ComputeHorde/raw/master/install_miner.sh | bash -s - production SSH_DESTINATION HOTKEY_PATH [MINER_PORT]
```

**Parameters:**
- `production` — mode (or `local` for testing)
- `SSH_DESTINATION` — e.g., `ubuntu@1.2.3.4`
- `HOTKEY_PATH` — e.g., `~/.bittensor/wallets/miner/hotkeys/default`
- `MINER_PORT` — optional, defaults to 8000

**Example:**
```bash
curl -sSfL https://github.com/backend-developers-ltd/ComputeHorde/raw/master/install_miner.sh \
  | bash -s - production ubuntu@203.0.113.50 ~/.bittensor/wallets/miner/hotkeys/default 8000
```

### 5.5 What the Install Script Does
1. **Validates arguments** — checks hotkey file exists, extracts wallet/hotkey names
2. **Creates tmpvars** on remote server with config variables + random admin password
3. **Transfers wallet files** — SCPs hotkey and coldkeypub to remote `.bittensor/wallets/`
4. **Installs Docker** — removes conflicting packages, installs Docker CE + Compose plugin
5. **Installs CUDA** — Linux headers, NVIDIA CUDA drivers, NVIDIA Container Toolkit
6. **Creates docker-compose.yml** with two services:
   - `miner-runner` — main miner app with wallet/socket mounts
   - `watchtower` — auto-update service for container images
7. **Generates .env** with DB creds, Bittensor network settings, port bindings, wallet refs
8. **Pulls and starts containers** — `docker compose up -d`
9. **Health check** — 10 attempts to hit `http://[host]:[port]/admin/login/`
10. **Outputs credentials** and admin login URL on success

---

## 6. Configuration Files

### 6.1 .env File (on miner server)
Located in the miner runner directory. Key variables:

```bash
# Security
SECRET_KEY=<random-50-char-string>          # python3 -c "from django.utils.crypto import get_random_string; print(get_random_string(50))"
POSTGRES_PASSWORD=<your-db-password>

# Network
BITTENSOR_MINER_PORT=8000                   # Must be open in firewall
BITTENSOR_MINER_ADDRESS=auto                # Auto-detects public IP
PORT_FOR_EXECUTORS=8000                     # Must match MINER_PORT unless nginx reconfigured
ADDRESS_FOR_EXECUTORS=172.17.0.1            # Docker bridge address

# Bittensor
BITTENSOR_NETUID=12                         # 12 for mainnet, 174 for testnet
BITTENSOR_NETWORK=finney                    # mainnet chain endpoint
BITTENSOR_WALLET_NAME=miner
BITTENSOR_WALLET_HOTKEY_NAME=default
HOST_WALLET_DIR=/home/ubuntu/.bittensor/wallets

# Auth
PYLON_IDENTITY_TOKEN=miner_token            # For pylon service communication
```

### 6.2 Docker Compose Services
The miner runner deploys:
- **postgres** — database
- **redis** — cache/queue
- **nginx** — reverse proxy
- **app** — main miner Django application
- **worker** — background task processing
- **pylon** — wallet operations and blockchain interactions (via bittensor-pylon)
- **watchtower** — auto-updates containers every 60 seconds

---

## 7. Executor Management (Competitive Edge)

### 7.1 Default Executor
The stock executor manager runs a **single executor** — this is NOT competitive for mainnet.

### 7.2 Custom Executor Manager (Required for Competitive Mining)
Create a Python class extending `BaseExecutorManager` with 4 methods:

```python
class MyExecutorManager(BaseExecutorManager):
    async def start_new_executor(self, ...):
        """Spawn a new executor instance"""
        pass

    async def kill_executor(self, ...):
        """Terminate an executor"""
        pass

    async def wait_for_executor(self, ...):
        """Wait for executor to become ready"""
        pass

    async def get_manifest(self, ...):
        """Report available executor capacity"""
        pass
```

Set in `.env`:
```bash
EXECUTOR_MANAGER_CLASS_PATH=my_module.MyExecutorManager
```

### 7.3 Remote Docker Executors
For multi-machine setups without custom code:
1. Create vendor directory: `/home/ubuntu/vendor`
2. Generate SSH key pairs for remote machines
3. Create YAML config with executor specifications
4. Set environment variables:
```bash
HOST_VENDOR_DIR=/home/ubuntu/vendor
DOCKER_EXECUTORS_CONFIG_PATH=/path/to/config.yaml
```

### 7.4 Docker Image Preloading
Job images must be pre-downloaded to prevent timeouts:
```bash
# Schedule as hourly cron job
*/60 * * * * /path/to/preload-job-images.sh
```

The `DYNAMIC_PRELOAD_DOCKER_JOB_IMAGES` env var lists frequently-used images.

---

## 8. Collateral Setup (For Organic Jobs)

### 8.1 Why Collateral
- Validators require collateral to assign paid organic jobs
- Creates economic incentive for honest computation
- Minimum: **0.01 TAO per validator** (increasing to 10 TAO)
- Gas reserve: ~0.2 TAO for transaction fees

### 8.2 Step-by-Step

**Create EVM (H160) wallet:**
```bash
python scripts/setup_evm.py --hotkey <YOUR_HOTKEY>
# Prints H160 address and associated SS58 address
```

**Fund the H160 wallet:**
```bash
btcli w transfer --wallet-name <COLDKEY> --recipient <SS58_ADDRESS> --amount 1.2
# 1.2 TAO = 1 TAO collateral + 0.2 TAO gas
```

**Find validator contracts:**
```bash
python scripts/list_contracts.py --netuid 12 --check-collateral --keyfile <H160_KEYFILE>
```

**Verify contract:**
```bash
python scripts/verify_contract.py --contract-address <ADDR> --expected-netuid 12 --expected-trustee <VALIDATOR_H160>
```

**Deposit collateral:**
```bash
python scripts/deposit_collateral.py --contract-address <ADDR> --amount-tao 1 --keyfile <H160_KEYFILE>
# Repeat for each trusted validator
```

**Withdraw (when leaving):**
```bash
python scripts/reclaim_collateral.py    # Initiate withdrawal
# Wait for deadline (5 days default)
python scripts/finalize_reclaim.py      # Complete withdrawal
python scripts/send_to_ss58_precompile.py  # Move TAO back to SS58 wallet
```

### 8.3 Slashing
- Automated by validator code — never human discretion
- Evidence stored on-chain (URLs + MD5 hashes)
- ~0.0005 TAO per slash transaction
- Miners can dispute via reclaim mechanism

---

## 9. Operational Commands

### Verify GPU Access
```bash
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

### Verify Miner Health
```bash
curl http://<ADDRESS>:<PORT>/admin/login/ -i
# Expected: HTTP/1.1 200 OK
```

### View Logs
```bash
docker compose logs -f          # All services
docker compose logs -f app      # Main app only
docker compose logs -f worker   # Background worker
```

### Restart Services
```bash
docker compose down --remove-orphans && docker compose up -d
```

### Update to Latest
Watchtower auto-updates every 60 seconds. For manual:
```bash
docker compose pull && docker compose down --remove-orphans && docker compose up -d
```

### Clear Persistent Data (Nuclear Option)
```bash
docker volume rm $(docker volume ls -q)
```

### Self-Test
Built-in testing simulates validator requests:
```bash
docker compose exec app python manage.py selftest
```

---

## 10. Monitoring

- **Grafana**: https://grafana.bactensor.io/d/subnet/metagraph-subnet?var-subnet=12
- **TaoStats**: https://taostats.io/subnets/12
- **TaoMarketCap**: https://taomarketcap.com/subnets/12

### Check Your Miner Status
```bash
btcli wallet overview --wallet.name miner --netuid 12
btcli subnet metagraph --netuid 12
```

---

## 11. DDoS Protection (Optional)

Install bt-ddos-shield as a separate Docker container:
- Repo: https://github.com/bactensor/bt-ddos-shield
- Protects miner endpoints from denial-of-service attacks
- Critical since validators from other subnets send tasks to your miner

---

## 12. Strategy Notes for Competitive Mining

1. **Custom executor manager** is mandatory for competitive mining — stock single-executor won't earn meaningful rewards
2. **Scale horizontally** — multiple A6000s, multiple machines behind one UID
3. **Preload Docker images** to reduce latency (scheduler as cron)
4. **Declare full capacity during peak cycles** — this is when scoring happens
5. **Maintain 10%+ of peak executors** outside peak to avoid 20% penalty
6. **Implement executor dancing** — rotate GPUs across UIDs for 10% bonus
7. **Deposit collateral** with top validators for organic job access (paid work)
8. **Monitor constantly** — Grafana dashboard, logs, metagraph position
9. **A6000 is the only game right now** — A100 support coming but not live yet
10. **Test on testnet (netuid 174) first** before committing mainnet registration cost

---

## 13. Key Links

| Resource | URL |
|----------|-----|
| GitHub Repo | https://github.com/backend-developers-ltd/ComputeHorde |
| Website | https://computehorde.io |
| SDK Docs | https://sdk.computehorde.io |
| Collateral Contracts | https://github.com/bactensor/collateral-contracts |
| DDoS Shield | https://github.com/bactensor/bt-ddos-shield |
| Pylon (blockchain comms) | https://github.com/backend-developers-ltd/bittensor-pylon |
| SubnetAlpha Profile | https://subnetalpha.ai/subnet/computehorde/ |
| Grafana Dashboard | https://grafana.bactensor.io/d/subnet/metagraph-subnet?var-subnet=12 |
| TaoStats | https://taostats.io/subnets/12 |
