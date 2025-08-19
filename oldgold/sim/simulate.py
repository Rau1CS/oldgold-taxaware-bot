"""Simulation CLI."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import List

from ..utils import save_json
from .v2_math import amount_out_v2, buy_cost_on_active_pool


def parse_grid(grid: str) -> List[float]:
    return [float(x) for x in grid.split(",") if x]


def main(
    stale_rin: float,
    stale_rout: float,
    fee: float,
    active_rin: float,
    active_rout: float,
    buy_tax: float,
    sell_tax: float,
    gas_base: float,
    slip_bps: float,
    grid: str,
) -> None:
    sizes = parse_grid(grid)
    results = []
    best = (0.0, float("-inf"))
    for x in sizes:
        base_out_stale = amount_out_v2(x, stale_rin, stale_rout, fee, sell_tax)
        base_in_active = buy_cost_on_active_pool(x, active_rin, active_rout, fee, buy_tax)
        pnl = base_out_stale - base_in_active - gas_base - abs(base_out_stale) * slip_bps / 1e4
        results.append(
            {
                "tokens": x,
                "base_out_stale": base_out_stale,
                "base_in_active": base_in_active,
                "pnl": pnl,
            }
        )
        if pnl > best[1]:
            best = (x, pnl)

    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    ts = int(time.time())
    save_json(out_dir / f"sim_{ts}.json", results)
    print(f"Best size {best[0]} with pnl {best[1]:.6f}")


def cli() -> None:  # pragma: no cover
    p = argparse.ArgumentParser()
    p.add_argument("--stale-rin", type=float, required=True)
    p.add_argument("--stale-rout", type=float, required=True)
    p.add_argument("--fee", type=float, default=0.003)
    p.add_argument("--active-rin", type=float, required=True)
    p.add_argument("--active-rout", type=float, required=True)
    p.add_argument("--buy-tax", type=float, default=0.0)
    p.add_argument("--sell-tax", type=float, default=0.0)
    p.add_argument("--gas-base", type=float, default=0.0)
    p.add_argument("--slip-bps", type=float, default=0.0)
    p.add_argument("--grid", default="1e3,1e4")
    args = p.parse_args()
    main(
        stale_rin=args.stale_rin,
        stale_rout=args.stale_rout,
        fee=args.fee,
        active_rin=args.active_rin,
        active_rout=args.active_rout,
        buy_tax=args.buy_tax,
        sell_tax=args.sell_tax,
        gas_base=args.gas_base,
        slip_bps=args.slip_bps,
        grid=args.grid,
    )


if __name__ == "__main__":  # pragma: no cover
    cli()
