#!/bin/bash
# SN33 CGP Miner launcher - sources .env then runs miner
cd /root/tao/sn33-cgp/cgp-subnet
source .env
exec /root/tao/sn33-cgp/cgp-subnet/venv/bin/python3 -m neurons.miner \
  --netuid 33 \
  --wallet.name tao_miner \
  --wallet.hotkey default \
  --axon.port 60000
