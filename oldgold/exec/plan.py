"""Planning stub."""
from __future__ import annotations

from ..sim.v2_math import amount_out_v2, buy_cost_on_active_pool


def plan(
    size_tokens: float,
    stale_rin: float,
    stale_rout: float,
    active_rin: float,
    active_rout: float,
    fee: float,
    buy_tax: float,
    sell_tax: float,
    gas_base: float,
    slip_bps: float,
) -> dict:
    base_out_stale = amount_out_v2(size_tokens, stale_rin, stale_rout, fee, sell_tax)
    base_in_active = buy_cost_on_active_pool(size_tokens, active_rin, active_rout, fee, buy_tax)
    pnl = base_out_stale - base_in_active - gas_base - abs(base_out_stale) * slip_bps / 1e4
    decision = "GO" if pnl > 0 else "NO-GO"
    return {"decision": decision, "pnl": pnl, "size": size_tokens if pnl > 0 else 0}
