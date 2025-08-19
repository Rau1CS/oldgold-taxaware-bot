"""Scan subgraph for candidate pairs."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

from ..config import OG_LIMIT, OG_MAX_PAGES, OG_MIN_LIQ_USD, SUBGRAPHS
from ..logging_conf import LOGGER
from ..utils import save_json
from .subgraph_client import post

BASE_SYMBOLS = {"WETH", "USDC", "USDT", "DAI", "WBNB"}


def fetch_pairs(endpoint: str) -> List[Dict]:
    query = Path(__file__).with_name("v2_pairs_query.graphql").read_text()
    pairs: List[Dict] = []
    for page in range(OG_MAX_PAGES):
        data = post(endpoint, query, {"skip": page * OG_LIMIT, "first": OG_LIMIT})
        part = data.get("pairs", [])
        if not part:
            break
        pairs.extend(part)
    return pairs


def score_pair(p: Dict) -> float:
    reserve = float(p.get("reserveUSD", 0))
    volume = float(p.get("volumeUSD", 0))
    return reserve / (volume + 100.0)


def filter_pairs(pairs: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    for p in pairs:
        if float(p.get("reserveUSD", 0)) < OG_MIN_LIQ_USD:
            continue
        t0 = p["token0"]["symbol"]
        t1 = p["token1"]["symbol"]
        if t0 in BASE_SYMBOLS or t1 in BASE_SYMBOLS:
            p = dict(p)
            p["score"] = score_pair(p)
            out.append(p)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def main(network: str = "eth_univ2") -> None:
    endpoint = SUBGRAPHS.get(network)
    if not endpoint:
        raise SystemExit(f"unknown network {network}")
    LOGGER.info("Fetching pairs from %s", endpoint)
    try:
        pairs = fetch_pairs(endpoint)
    except Exception as exc:  # pragma: no cover - network issues
        LOGGER.error("scan failed: %s", exc)
        pairs = []
    pairs = filter_pairs(pairs)[:100]

    out_path = Path("out")
    out_path.mkdir(exist_ok=True)
    out_file = out_path / f"scan_{network}.json"
    save_json(out_file, pairs)

    LOGGER.info("Top 20 pairs:")
    for i, p in enumerate(pairs[:20], 1):
        LOGGER.info("%2d %s score=%.2f reserveUSD=%.2f", i, p["id"], p["score"], float(p["reserveUSD"]))


def cli() -> None:  # pragma: no cover - wrapper for scripts
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", default="eth_univ2")
    args = parser.parse_args()
    main(network=args.network)


if __name__ == "__main__":  # pragma: no cover
    cli()
