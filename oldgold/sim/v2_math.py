"""V2 constant product math with taxes."""
from __future__ import annotations


def amount_out_v2(amount_in_nominal: float, R_in: float, R_out: float, fee: float, sell_tax: float) -> float:
    """Amount out for a V2 swap with input-side tax."""
    eff_in = amount_in_nominal * (1 - sell_tax)
    amount_in_with_fee = eff_in * (1 - fee)
    return (amount_in_with_fee * R_out) / (R_in + amount_in_with_fee)


def buy_cost_on_active_pool(
    tokens_out_target: float,
    token_reserve: float,
    base_reserve: float,
    fee: float,
    buy_tax: float,
    tol: float = 1e-9,
) -> float:
    """Return base needed on active pool to receive target tokens after tax."""

    def tokens_out(base_in: float) -> float:
        out = amount_out_v2(base_in, base_reserve, token_reserve, fee, 0.0)
        return out * (1 - buy_tax)

    lo, hi = 0.0, base_reserve * 1e6
    for _ in range(128):
        mid = (lo + hi) / 2
        if tokens_out(mid) < tokens_out_target:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return hi
