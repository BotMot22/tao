# TAO - Bittensor Multi-Subnet Miner

Mining infrastructure for Bittensor subnets, ordered by profitability (hardest → easiest).

## Subnets

| Priority | Subnet | Task | Hardware | Daily TAO (est.) |
|----------|--------|------|----------|-----------------|
| 1 | **SN64 Chutes** | Serverless GPU inference | A100/H100 + K8s | 0.3-1.0+ |
| 2 | **SN12 ComputeHorde** | GPU compute rental | A6000 | 0.1-0.5 |
| 3 | **SN8 Taoshi/Vanta** | Futures trading signals | CPU only (2vCPU/8GB) | PnL-based |
| 4 | **SN27 Compute** | Decentralized GPU compute | RTX 4090+ bare metal | 0.05-0.3 |

## Structure

```
tao/
├── sn64-chutes/        # Kubernetes-based GPU inference platform
│   ├── setup.sh        # Bootstrap script
│   ├── inventory.yml   # Ansible inventory template
│   ├── values.yaml     # Helm chart values
│   └── gepetto.py      # Deployment strategy (competitive edge)
├── sn12-computehorde/  # GPU compute executor management
│   ├── setup.sh        # Bootstrap script
│   └── config.env      # Environment config
├── sn08-vanta/         # Futures trading signal miner
│   ├── setup.sh        # Bootstrap script
│   ├── strategy.py     # Trading strategy (sends signals to miner API)
│   └── api_keys.json   # Local API auth
├── sn27-compute/       # Bare metal GPU compute
│   ├── setup.sh        # Bootstrap script
│   └── config.env      # Environment config
├── shared/
│   ├── wallet.sh       # Wallet creation helper
│   ├── monitor.sh      # Cross-subnet monitoring
│   └── register.sh     # Subnet registration helper
└── README.md
```

## Quick Start

```bash
# 1. Install bittensor
pip install bittensor

# 2. Create wallet
bash shared/wallet.sh

# 3. Pick a subnet and run its setup
cd sn27-compute && bash setup.sh   # easiest start
```

## Post-Halving Economics (March 2026)

- **Network emission**: ~3,600 TAO/day (halved Dec 2025)
- **Miner share**: 41% = ~1,476 TAO/day across all subnets
- **dTAO**: Miners earn subnet alpha tokens, swap to TAO
- **Max UIDs per subnet**: 256 (192 miners + 64 validators)
