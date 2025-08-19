#!/bin/bash
set -euo pipefail
python -m oldgold.sim.simulate \
  --stale-rin 1000000 --stale-rout 80 --fee 0.003 \
  --active-rin 100000000 --active-rout 200 \
  --buy-tax 0.05 --sell-tax 0.05 \
  --gas-base 0.002 --slip-bps 20 \
  --grid "1e3,1e4,1e5,1e6"
