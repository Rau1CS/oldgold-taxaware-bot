from oldgold.sim.v2_math import amount_out_v2, buy_cost_on_active_pool


def test_bisection_monotonic():
    cost_small = buy_cost_on_active_pool(10, 1000, 100, 0.003, 0.0)
    cost_big = buy_cost_on_active_pool(20, 1000, 100, 0.003, 0.0)
    assert cost_big > cost_small


def test_pnl_decreases_with_costs():
    def pnl(buy_tax, sell_tax, gas):
        base_out_stale = amount_out_v2(1000, 1_000_000, 80, 0.003, sell_tax)
        base_in_active = buy_cost_on_active_pool(1000, 100_000_000, 200, 0.003, buy_tax)
        return base_out_stale - base_in_active - gas

    base = pnl(0, 0, 0)
    worse = pnl(0.05, 0.05, 1)
    assert worse < base
