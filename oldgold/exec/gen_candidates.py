"""
Generate candidate tokens from a V2 subgraph (read-only; no swaps).

Heuristic per token/base pair:
- reserveUSD >= --min-reserve-usd
- 24h volume <= --max-24h-usd
- 7d volume <= --max-7d-usd
- (optional) age_since_activity_days >= --min-age-days

Outputs:
- out/candidates_<chain>_<base>.json (sorted by 'score')
- tokens.txt (deduped token list to feed discover/probing)

Usage example:
  python -m oldgold.exec.gen_candidates \
    --chain bsc --base WBNB \
    --subgraph $SUBGRAPH_BSC_UNIV2 \
    --min-reserve-usd 5000 --max-24h-usd 50 --max-7d-usd 250 \
    --pages 10 --page-size 200 --top 150
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

import requests

from ..config import CHAIN_CONFIGS
from ..logging_conf import LOGGER

DEFAULT_SUBGRAPHS = {
    # You can override via CLI --subgraph
    "eth": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2",
    # Example Pancake v2 endpoint (update if you have a better one / hosted mirror)
    "bsc": "https://bsc.streamingfast.io/subgraphs/name/pancakeswap/exchange-v2",
}

PAIRS_QUERY = """
query Pairs($skip:Int!,$first:Int!){
  pairs(skip:$skip, first:$first, orderBy: reserveUSD, orderDirection: desc){
    id
    reserveUSD
    token0{ id symbol decimals }
    token1{ id symbol decimals }
  }
}
"""

# We'll query day data per pair to avoid fetching huge global windows.
PAIR_DAY_QUERY = """
query PairDay($pair:String!,$first:Int!){
  pairDayDatas(first:$first, orderBy: date, orderDirection: desc, where:{pairAddress:$pair}){
    date
    dailyVolumeUSD
    reserveUSD
  }
}
"""

BASE_SYMBOLS = {"WETH", "WBNB", "USDC", "USDT", "DAI"}


def post(endpoint: str, query: str, variables: dict, tries: int = 3) -> dict:
    last = None
    for i in range(tries):
        try:
            r = requests.post(endpoint, json={"query": query, "variables": variables}, timeout=30)
            r.raise_for_status()
            data = r.json()
            if "errors" in data:
                raise RuntimeError(data["errors"])
            return data["data"]
        except Exception as e:
            last = e
            time.sleep(0.4 * (2**i))
    raise RuntimeError(f"GraphQL error after retries: {last}")


def is_base(addr_or_symbol: str, chain: str, base_symbol: str) -> bool:
    # Accept either exact symbol match or exact address match against chain config
    v = addr_or_symbol
    cfg = CHAIN_CONFIGS[chain]
    if base_symbol.upper() in {"WBNB", "WETH"} and v.lower().startswith("0x"):
        # compare to wrapped address in config
        return v.lower() == cfg.wrapped.lower()
    return v.upper() == base_symbol.upper()


def pick_token_side(p: dict, chain: str, base_symbol: str) -> Tuple[str, str]:
    """Return (token_addr, base_addr) if the pair includes the base; else ('','')."""
    t0, t1 = p["token0"], p["token1"]
    if is_base(t0["symbol"], chain, base_symbol) or is_base(t0["id"], chain, base_symbol):
        return (t1["id"], t0["id"])
    if is_base(t1["symbol"], chain, base_symbol) or is_base(t1["id"], chain, base_symbol):
        return (t0["id"], t1["id"])
    return ("", "")


def summarize_daydata(days: List[dict]) -> Tuple[float, float, float]:
    """Return (vol_24h, vol_7d, age_since_activity_days).

    age_since_activity_days: days since last day with dailyVolumeUSD > 0
    """
    vol_24h = float(days[0]["dailyVolumeUSD"]) if days else 0.0
    vol_7d = sum(float(d["dailyVolumeUSD"]) for d in days[:7])
    age_days = 0.0
    for i, d in enumerate(days):
        if float(d["dailyVolumeUSD"]) > 0:
            age_days = i  # 'i' days ago had last activity
            break
    else:
        age_days = len(days) if days else math.inf
    return vol_24h, vol_7d, age_days


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", default="bsc")
    ap.add_argument("--base", default="WBNB")
    ap.add_argument("--subgraph", help="Override subgraph URL (optional)")
    ap.add_argument("--pages", type=int, default=8, help="How many pages to walk")
    ap.add_argument("--page-size", type=int, default=200, help="Pairs per page")
    ap.add_argument("--min-reserve-usd", type=float, default=5_000)
    ap.add_argument("--max-24h-usd", type=float, default=50)
    ap.add_argument("--max-7d-usd", type=float, default=250)
    ap.add_argument("--min-age-days", type=float, default=3.0,
                    help="Days since last activity (0 disables the check)")
    ap.add_argument("--top", type=int, default=150)
    args = ap.parse_args()

    chain = args.chain
    endpoint = args.subgraph or DEFAULT_SUBGRAPHS.get(chain)
    if not endpoint:
        raise SystemExit(f"No subgraph for chain={chain}. Use --subgraph.")

    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)

    # 1) Page through top pairs by reserveUSD
    pairs: List[dict] = []
    for pg in range(args.pages):
        data = post(endpoint, PAIRS_QUERY, {"skip": pg * args.page_size, "first": args.page_size})
        page_pairs = data.get("pairs", [])
        if not page_pairs:
            break
        pairs.extend(page_pairs)

    LOGGER.info("Fetched %d pairs from subgraph", len(pairs))

    # 2) Filter for pairs that include the selected base
    candidates = []
    for p in pairs:
        token_addr, base_addr = pick_token_side(p, chain, args.base)
        if not token_addr:
            continue
        reserve_usd = float(p["reserveUSD"] or 0)
        if reserve_usd < args.min_reserve_usd:
            continue

        # 3) Pull recent day data (last ~14 days) for staleness
        try:
            dd = post(endpoint, PAIR_DAY_QUERY, {"pair": p["id"], "first": 14}).get("pairDayDatas", [])
        except Exception as e:
            LOGGER.warning("pairDayDatas failed for %s: %s", p["id"], e)
            dd = []

        vol_24h, vol_7d, age_days = summarize_daydata(dd)

        # 4) Apply thresholds (low recent volume, optionally old activity)
        if vol_24h > args.max_24h_usd:
            continue
        if vol_7d > args.max_7d_usd:
            continue
        if args.min_age_days > 0 and age_days < args.min_age_days:
            continue

        # score: more reserves, older last activity = better
        score = reserve_usd / (vol_7d + 1.0) * (1.0 + age_days / 7.0)

        candidates.append(
            {
                "pair": p["id"],
                "token": token_addr,
                "base": base_addr,
                "reserveUSD": reserve_usd,
                "vol_24h": vol_24h,
                "vol_7d": vol_7d,
                "age_days": age_days,
                "score": score,
            }
        )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    top_rows = candidates[: args.top]

    # 5) Write outputs
    json_path = out_dir / f"candidates_{chain}_{args.base}.json"
    with open(json_path, "w") as f:
        json.dump(top_rows, f, indent=2)
    LOGGER.info("wrote %s (%d rows)", json_path, len(top_rows))

    # tokens.txt (dedupe)
    toks = []
    seen = set()
    for r in top_rows:
        t = r["token"].lower()
        if t not in seen:
            toks.append(t); seen.add(t)
    tokens_path = Path("tokens.txt")
    with open(tokens_path, "w") as f:
        f.write("\n".join(toks) + "\n")
    LOGGER.info("wrote %s (%d tokens)", tokens_path, len(toks))


if __name__ == "__main__":  # pragma: no cover
    main()
