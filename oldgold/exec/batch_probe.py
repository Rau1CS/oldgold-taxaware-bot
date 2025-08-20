"""Batch probe top candidates and simulate with measured taxes.

Input: out/discover_<chain>_<base>.json (from discover.py)
Steps:
  - Take top N rows
  - For each: live tax probe (dust buy & sell)
  - Simulate with taxes + gas, produce GO/NO-GO summary
Output: out/ranked_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import List, Dict

from ..logging_conf import LOGGER
from ..utils import save_json
from ..tax.probe import main as probe_main
from .run_one import run_sim
from .run_one import estimate_gas_base  # reuse your function

MIN_PNL = float(os.getenv("MIN_PNL_BASE", "0.002"))
MAX_TAX_BUY = float(os.getenv("MAX_TAX_BUY", "0.15"))
MAX_TAX_SELL = float(os.getenv("MAX_TAX_SELL", "0.15"))

def load_rows(path: str) -> List[Dict]:
    return json.loads(Path(path).read_text())

def decide(pnl: float, buy_tax: float, sell_tax: float, honeypots: tuple[bool,bool]) -> tuple[str, List[str]]:
    reasons: List[str] = []
    if honeypots[0]:
        reasons.append("honeypot_buy")
    if honeypots[1]:
        reasons.append("honeypot_sell")
    if buy_tax > MAX_TAX_BUY:
        reasons.append("buy_tax_high")
    if sell_tax > MAX_TAX_SELL:
        reasons.append("sell_tax_high")
    if pnl < MIN_PNL:
        reasons.append("pnl_below_min")
    return ("GO" if not reasons else "NO-GO", reasons)

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--chain", default="bsc")
    p.add_argument("--infile", required=True)  # discover_<chain>_<base>.json
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--fee", type=float, default=0.003)
    p.add_argument("--slip-bps", type=float, default=20.0)
    p.add_argument("--grid", default="1e3,5e3,1e4")
    p.add_argument("--dust", type=float, default=float(os.getenv("DUST_BASE", "0.00015")))
    args = p.parse_args()

    rows = load_rows(args.infile)[: args.top]
    out_rows: List[Dict] = []

    gas_base = estimate_gas_base(args.chain)

    for r in rows:
        token = r["token"]
        LOGGER.info("Probing %s", token)
        try:
            probe = probe_main(chain=args.chain, token=token, dust=args.dust) or {}
        except SystemExit as se:
            LOGGER.warning("probe skipped %s: %s", token, se)
            probe = {"buy_tax_est": 0.0, "sell_tax_est": 0.0, "honeypot_buy": True, "honeypot_sell": True}

        buy_tax = float(probe.get("buy_tax_est", 0.0) or 0.0)
        sell_tax = float(probe.get("sell_tax_est", 0.0) or 0.0)
        hp_buy = bool(probe.get("honeypot_buy", False))
        hp_sell = bool(probe.get("honeypot_sell", False))

        sim = run_sim(
            stale_rin=r["stale_rin"],
            stale_rout=r["stale_rout"],
            active_rin=r["active_rin"],
            active_rout=r["active_rout"],
            fee=args.fee,
            slip_bps=args.slip_bps,
            grid=args.grid,
            buy_tax=buy_tax,
            sell_tax=sell_tax,
            gas_base=gas_base,
        )

        decision, reasons = decide(sim["best"]["pnl"], buy_tax, sell_tax, (hp_buy, hp_sell))

        out_rows.append(
            {
                "token": token,
                "stale_pair": r["stale_pair"],
                "active_pair": r["active_pair"],
                "edge_bps": r["edge_bps"],
                "buy_tax": buy_tax,
                "sell_tax": sell_tax,
                "honeypot_buy": hp_buy,
                "honeypot_sell": hp_sell,
                "gas_base": gas_base,
                "best_size": sim["best"]["size"],
                "best_pnl": sim["best"]["pnl"],
                "decision": decision,
                "reasons": reasons,
            }
        )

    Path("out").mkdir(exist_ok=True)
    out_file = Path("out") / f"ranked_{int(time.time())}.json"
    save_json(out_file, out_rows)
    LOGGER.info("wrote %s", out_file)
    # print short table
    for row in out_rows:
        LOGGER.info("%s  edge=%.1f bps  pnl=%.6f  taxes=(%.2f/%.2f)  %s %s",
                    row["token"], row["edge_bps"], row["best_pnl"], row["buy_tax"], row["sell_tax"],
                    row["decision"], (";".join(row["reasons"]) if row["reasons"] else ""))

if __name__ == "__main__":  # pragma: no cover
    main()
