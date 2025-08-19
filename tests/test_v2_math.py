from oldgold.sim.v2_math import amount_out_v2, buy_cost_on_active_pool
import pytest


def test_no_tax_matches_classic_v2():
    amt = amount_out_v2(100, 1000, 500, 0.003, 0.0)
    expected = (100 * (1 - 0.003) * 500) / (1000 + 100 * (1 - 0.003))
    assert amt == pytest.approx(expected)


def test_full_sell_tax_zero_out():
    assert amount_out_v2(100, 1000, 500, 0.003, 1.0) == 0


def test_monotonic_increasing():
    a1 = amount_out_v2(10, 1000, 500, 0.003, 0.0)
    a2 = amount_out_v2(20, 1000, 500, 0.003, 0.0)
    assert a2 > a1
