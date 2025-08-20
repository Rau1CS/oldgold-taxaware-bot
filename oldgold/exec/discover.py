"""Discover promising token/base pairs without spending funds.

For each token:
  - Fetch token->base reserves on the 'stale' pair (sell target).
  - Pick an 'active' pair (deepest) if available; else reuse stale.
  - Compute mid-price gap and no-tax theoretical PnL over a small grid.
  - Keep rows that clear min edge and gas hurdles, then rank & save.

Outputs: out/discover_<chain>_<base>.json
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, List, Dict

from web3 import Web3

from ..config import CHAIN_CONFIGS
from ..logging_conf import LOGGER
from ..utils import save_json
from ..sim.v2_math import amount_out_v2, buy_cost_on_active_pool
from ..scanner.pairs import get_pair, active_pool_for_token

# Local gas estimate (same idea as run_one)
APPROVE_GAS = int(os.getenv("GAS_UNITS_APPROVE", "50000"))
SWAP_GAS = int(os.getenv("GAS_UNITS_SWAP", "200000"))

PAIR_ABI = json.loads(
    """[
      {"name":"token0","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"},
      {"name":"token1","outputs":[{"type":"address"}],"stateMutability":"view","type":"function"},
      {"name":"getReserves","outputs":[{"type":"uint112"},{"type":"uint112"},{"type":"uint32"}],"stateMutability":"view","type":"function"}
    ]"""
)

def _w3(chain: str) -> Web3:
    return Web3(Web3.HTTPProvider(CHAIN_CONFIGS[chain].rpc))


def _estimate_gas_base(chain: str) -> float:
    try:
        w3 = _w3(chain)
        gp = w3.eth.gas_price
    except Exception:
        return 0.0
    units = APPROVE_GAS + 2 * SWAP_GAS
    return float(Web3.from_wei(gp * units, "ether"))


def _to_checksum(addr: str) -> str:
    return Web3.to_checksum_address(addr)


def _reserves_from_pair_addr(chain: str, pair_addr: str, token_in: str) -> tuple[float, float]:
    """Read reserves for token_in -> other from a known pair address."""
    w3 = _w3(chain)
    c = w3.eth.contract(address=_to_checksum(pair_addr), abi=PAIR_ABI)
    t0 = c.functions.token0().call()
    _t1 = c.functions.token1().call()
    r0, r1, _ = c.functions.getReserves().call()
    if _to_checksum(token_in) == _to_checksum(t0):
        return float(r0), float(r1)
    else:
        return float(r1), float(r0)


def _load_tokens(tokens_file: str | None, tokens_csv: str | None) -> List[str]:
    if tokens_file:
        text = Path(tokens_file).read_text().strip()
        addrs = [x.strip() for x in text.replace(",", "\n").splitlines() if x.strip()]
        return addrs
    if tokens_csv:
        return [x.strip() for x in tokens_csv.split(",") if x.strip()]
    raise SystemExit("Provide --tokens-file or --tokens (comma-separated)")


def discover(
    chain: str,
    base: str,
    tokens: Iterable[str],
    min_edge_bps: float,
    fee: float,
    grid: List[float],
    top: int,
) -> List[Dict]:
    cfg = CHAIN_CONFIGS[chain]
    base_addr = base if base.lower().startswith("0x") else cfg.wrapped
    base_addr = _to_checksum(base_addr)

    gas_base_est = _estimate_gas_base(chain)
    rows: List[Dict] = []

    for token in tokens:
        try:
            token = _to_checksum(token)
            # stale (sell) reserves: token -> base
            stale = get_pair(chain, token, base_addr)
            # try to find a deeper 'active' pool by address; otherwise reuse stale reserves
            active_addr = active_pool_for_token(chain, token, base_addr) or stale.address
            try:
                a_rin, a_rout = _reserves_from_pair_addr(chain, active_addr, token)
            except Exception:
                a_rin, a_rout = stale.r_in, stale.r_out

            # mid prices (token->base)
            p_stale = stale.r_out / stale.r_in if stale.r_in > 0 else 0.0
            p_active = a_rout / a_rin if a_rin > 0 else 0.0
            if p_stale <= 0 or p_active <= 0:
                continue

            edge_bps = 1e4 * (p_stale / p_active - 1.0)

            if edge_bps < min_edge_bps:
                continue

            # no-tax pnl over small grid
            best_no_tax = float("-inf")
            best_size = 0.0
            for x in grid:
                base_out_stale = amount_out_v2(x, stale.r_in, stale.r_out, fee, 0.0)
                base_in_active = buy_cost_on_active_pool(x, a_rin, a_rout, fee, 0.0)
                pnl = base_out_stale - base_in_active - gas_base_est
                if pnl > best_no_tax:
                    best_no_tax, best_size = pnl, x

            # quick hurdle: pnl must beat gas by 20%
            if best_no_tax < gas_base_est * 1.2:
                continue

            rows.append(
                {
                    "token": token,
                    "base": base_addr,
                    "stale_pair": stale.address,
                    "active_pair": active_addr,
                    "stale_rin": stale.r_in,
                    "stale_rout": stale.r_out,
                    "active_rin": a_rin,
                    "active_rout": a_rout,
                    "p_stale": p_stale,
                    "p_active": p_active,
                    "edge_bps": edge_bps,
                    "gas_base_est": gas_base_est,
                    "best_no_tax": best_no_tax,
                    "best_size_no_tax": best_size,
                }
            )
        except Exception as e:
            LOGGER.warning("discover skip %s: %s", token, e)
            continue

    rows.sort(key=lambda r: r["edge_bps"], reverse=True)
    return rows[:top]


def parse_grid(s: str) -> List[float]:
    return [float(x) for x in s.split(",") if x.strip()]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--chain", default="bsc")
    p.add_argument("--base", default="WBNB")
    p.add_argument("--tokens-file")  # newline or CSV of token addresses
    p.add_argument("--tokens")  # comma-separated list
    p.add_argument("--min-edge-bps", type=float, default=400.0)
    p.add_argument("--fee", type=float, default=0.003)
    p.add_argument("--grid", default="1e3,1e4,1e5")
    p.add_argument("--top", type=int, default=100)
    p.add_argument("--print", dest="nprint", type=int, default=20)
    args = p.parse_args()

    tokens = _load_tokens(args.tokens_file, args.tokens)
    rows = discover(
        chain=args.chain,
        base=args.base,
        tokens=tokens,
        min_edge_bps=args.min_edge_bps,
        fee=args.fee,
        grid=parse_grid(args.grid),
        top=args.top,
    )
    out = Path("out")
    out.mkdir(exist_ok=True)
    outfile = out / f"discover_{args.chain}_{args.base}.json"
    save_json(outfile, rows)
    LOGGER.info("wrote %s (%d rows)", outfile, len(rows))
    for r in rows[: args.nprint]:
        LOGGER.info("%s edge=%.1f bps no-tax=%.6f stale=%s active=%s",
                    r["token"], r["edge_bps"], r["best_no_tax"], r["stale_pair"], r["active_pair"])


if __name__ == "__main__":  # pragma: no cover
    main()
