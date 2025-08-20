"""End-to-end single opportunity simulation.

This module glues together pair discovery, gas estimation and the
existing simulation utilities into a single command.  It is intentionally
minimal and network operations are best-effort, falling back to default
values when data cannot be fetched.
"""
from __future__ import annotations

from pathlib import Path
import json
import os

from web3 import Web3

from ..config import CHAIN_CONFIGS
from ..logging_conf import LOGGER
from ..scanner.pairs import active_pool_for_token, get_pair
from ..sim.v2_math import amount_out_v2, buy_cost_on_active_pool
from ..sim.simulate import parse_grid
from ..utils import save_json, retry_call
from ..data.tokens import TOKENS_BY_CHAIN

APPROVE_GAS = 50_000
SWAP_GAS = 200_000


def _w3(chain: str) -> Web3:
    cfg = CHAIN_CONFIGS[chain]
    return Web3(Web3.HTTPProvider(cfg.rpc))


def estimate_gas_base(chain: str) -> float:
    """Estimate gas cost in native base units."""

    try:
        w3 = _w3(chain)
        gas_price = retry_call(3, lambda: w3.eth.gas_price)
    except Exception:  # pragma: no cover - network dependent
        return 0.0
    total_units = APPROVE_GAS + 2 * SWAP_GAS
    return float(Web3.from_wei(gas_price * total_units, "ether"))


def resolve_base_addr(chain: str, base: str) -> str:
    if base.lower().startswith("0x"):
        return Web3.to_checksum_address(base)
    m = TOKENS_BY_CHAIN.get(chain, {})
    if base.upper() in m:
        return Web3.to_checksum_address(m[base.upper()])
    return Web3.to_checksum_address(CHAIN_CONFIGS[chain].wrapped)


def run_sim(
    stale_rin: float,
    stale_rout: float,
    active_rin: float,
    active_rout: float,
    fee: float,
    slip_bps: float,
    grid: str,
    buy_tax: float = 0.0,
    sell_tax: float = 0.0,
    gas_base: float = 0.0,
) -> dict:
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
    return {"results": results, "best": {"size": best[0], "pnl": best[1]}}


def main(
    chain: str = "bsc",
    token: str = "",
    base: str = "WBNB",
    stale_pair: str | None = None,
    active_pair: str = "auto",
    fee: float = 0.003,
    slip_bps: float = 20.0,
    grid: str = "1e3,5e3,1e4",
    dry_run: bool = False,
    force_probe: bool = False,
) -> None:
    if not token:
        raise SystemExit("token is required")

    base_addr = resolve_base_addr(chain, base)

    deny_path = Path(__file__).resolve().parent.parent / "data" / "denylists.json"
    try:
        deny = json.loads(deny_path.read_text())
    except FileNotFoundError:  # pragma: no cover - optional file
        deny = {"tokens": [], "pairs": []}
    if token.lower() in {t.lower() for t in deny.get("tokens", [])}:
        LOGGER.warning("token %s is denylisted", token)
        return

    stale = get_pair(chain, token, base_addr)
    if stale_pair:
        stale.address = stale_pair

    if active_pair == "auto" or not active_pair:
        active_addr = active_pool_for_token(chain, token, base_addr) or stale.address
    else:
        active_addr = active_pair
    active = get_pair(chain, token, base_addr)
    active.address = active_addr

    from ..tax.probe import main as probe_main

    tax = {}
    try:
        tax = probe_main(chain=chain, token=token, dry_run=dry_run, force_probe=force_probe) or {}
    except Exception as e:  # pragma: no cover - network dependent
        LOGGER.warning("probe failed: %s (continuing with 0%% taxes)", e)
    buy_tax = float(tax.get("buy_tax_est", 0.0) or 0.0)
    sell_tax = float(tax.get("sell_tax_est", 0.0) or 0.0)

    gas_base = estimate_gas_base(chain)

    sim = run_sim(
        stale_rin=stale.r_in,
        stale_rout=stale.r_out,
        active_rin=active.r_in,
        active_rout=active.r_out,
        fee=fee,
        slip_bps=slip_bps,
        grid=grid,
        gas_base=gas_base,
        buy_tax=buy_tax,
        sell_tax=sell_tax,
    )

    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"run_one_{token.lower()}.json"
    payload = {
        "token": token,
        "base": base_addr,
        "stale_pair": stale.address,
        "active_pair": active.address,
        "gas_base_used": gas_base,
        **sim,
    }

    MIN_PNL = float(os.getenv("MIN_PNL_BASE", "0.002"))
    MAX_TAX_BUY = float(os.getenv("MAX_TAX_BUY", "0.15"))
    MAX_TAX_SELL = float(os.getenv("MAX_TAX_SELL", "0.15"))

    reasons: list[str] = []
    if buy_tax > MAX_TAX_BUY:
        reasons.append("buy_tax_high")
    if sell_tax > MAX_TAX_SELL:
        reasons.append("sell_tax_high")
    if sim["best"]["pnl"] < MIN_PNL:
        reasons.append("pnl_below_min")

    decision = "GO" if not reasons else "NO-GO"
    payload["decision"] = decision
    payload["reasons"] = reasons

    save_json(out_file, payload)
    LOGGER.info("Best size %s with pnl %.6f", sim["best"]["size"], sim["best"]["pnl"])

    summary = {
        "chain": chain,
        "token": token,
        "stale": stale.address,
        "active": active.address,
        "gas_base": gas_base,
        "buy_tax": buy_tax,
        "sell_tax": sell_tax,
        "best_size": sim["best"]["size"],
        "pnl": sim["best"]["pnl"],
        "decision": decision,
    }
    print(json.dumps({"oldgold_summary": summary}, separators=(",", ":")))


if __name__ == "__main__":  # pragma: no cover - manual use
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--chain", default="bsc")
    p.add_argument("--token", required=True)
    p.add_argument("--base", default="WBNB")
    p.add_argument("--stale-pair")
    p.add_argument("--active-pair", default="auto")
    p.add_argument("--fee", type=float, default=0.003)
    p.add_argument("--slip-bps", type=float, default=20.0)
    p.add_argument("--grid", default="1e3,5e3,1e4")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force-probe", action="store_true")
    a = p.parse_args()
    main(
        chain=a.chain,
        token=a.token,
        base=a.base,
        stale_pair=a.stale_pair,
        active_pair=a.active_pair,
        fee=a.fee,
        slip_bps=a.slip_bps,
        grid=a.grid,
        dry_run=a.dry_run,
        force_probe=a.force_probe,
    )
