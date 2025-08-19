# OldGold Tax-Aware Bot

This project finds stale Uniswap V2-style pools, measures fee-on-transfer taxes with dust swaps, and simulates tax-aware arbitrage (buy on active market, sell into stale pool), outputting ranked opportunities.

## Quickstart (2-minute path)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set RPCs (no PK needed for scan)
make scan
# Optional (live dust probe):
# export PK=0x... (fund a tiny amount on BSC)
make probe TOKEN=0xTOKEN CHAIN=bsc
# Simulation example:
make simulate
```

## Architecture

Scanner → Probe → Simulate → Plan. The scanner fetches candidate pairs from subgraphs. Probe performs dust swaps to estimate token taxes. Simulation models an arbitrage between an active and a stale pool with taxes, gas and slippage. Planner is a stub that would decide whether to execute.

## Safety

* Dust only; use cheap chains.
* Fee-on-transfer tokens can be honeypots.
* No execution on chain in this MVP – planning only.

## Roadmap

* Private relay execution
* Uniswap V3 range support
* Flashloans and batching
* Blacklist filters

## License

MIT
