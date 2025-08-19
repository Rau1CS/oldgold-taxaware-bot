"""Command line interface for OldGold."""
from __future__ import annotations

import argparse
from typing import List


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="oldgold")
    sub = p.add_subparsers(dest="cmd")

    scan_p = sub.add_parser("scan")
    scan_p.add_argument("--network", default="eth_univ2")

    probe_p = sub.add_parser("probe")
    probe_p.add_argument("--chain", default="bsc")
    probe_p.add_argument("--token", required=True)
    probe_p.add_argument("--dust", type=float, default=0.0002)

    sim_p = sub.add_parser("simulate")
    sim_p.add_argument("--stale-rin", type=float, required=True)
    sim_p.add_argument("--stale-rout", type=float, required=True)
    sim_p.add_argument("--fee", type=float, default=0.003)
    sim_p.add_argument("--active-rin", type=float, required=True)
    sim_p.add_argument("--active-rout", type=float, required=True)
    sim_p.add_argument("--buy-tax", type=float, default=0.0)
    sim_p.add_argument("--sell-tax", type=float, default=0.0)
    sim_p.add_argument("--gas-base", type=float, default=0.0)
    sim_p.add_argument("--slip-bps", type=float, default=0.0)
    sim_p.add_argument("--grid", default="1e3,1e4")

    return p


def main(argv: List[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    if args.cmd == "scan":
        from .scanner.scan import main as scan_main

        scan_main(network=args.network)
    elif args.cmd == "probe":
        from .tax.probe import main as probe_main

        probe_main(chain=args.chain, token=args.token, dust=args.dust)
    elif args.cmd == "simulate":
        from .sim.simulate import main as sim_main

        sim_main(
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
    else:
        p.print_help()
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
