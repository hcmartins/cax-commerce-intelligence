import pytest

from app.modules.profitability.calculator import (
    build_rationale,
    calculate_profitability,
    compute_landed_cost,
    compute_margin_pct,
    compute_marketplace_fee,
    compute_profit,
    compute_roi_pct,
    determine_decision,
)
from app.modules.profitability.models import Decision


def test_compute_landed_cost_splits_shipping_across_moq():
    # unit_price=4.00 + (800 shipping / 1000 units) = 4.80
    assert compute_landed_cost(unit_price=4.0, shipping_cost=800.0, moq=1000) == 4.80


def test_compute_landed_cost_handles_zero_moq_without_dividing_by_zero():
    assert compute_landed_cost(unit_price=4.0, shipping_cost=800.0, moq=0) == 4.0


def test_compute_landed_cost_handles_missing_shipping_cost():
    assert compute_landed_cost(unit_price=4.0, shipping_cost=None, moq=100) == 4.0


def test_compute_landed_cost_includes_other_costs():
    assert compute_landed_cost(unit_price=4.0, shipping_cost=0.0, moq=1, other_costs=1.5) == 5.5


def test_compute_marketplace_fee():
    assert compute_marketplace_fee(selling_price=20.0, fee_pct=18.0) == 3.6


def test_compute_profit():
    assert compute_profit(selling_price=20.0, landed_cost=4.8, marketplace_fee=3.6) == 11.6


def test_compute_margin_pct():
    assert compute_margin_pct(profit=11.6, selling_price=20.0) == 58.0


def test_compute_margin_pct_zero_selling_price_does_not_divide_by_zero():
    assert compute_margin_pct(profit=-1.0, selling_price=0.0) == 0.0


def test_compute_roi_pct():
    assert compute_roi_pct(profit=11.6, landed_cost=4.8) == pytest.approx(241.67, abs=0.01)


def test_compute_roi_pct_zero_landed_cost_does_not_divide_by_zero():
    assert compute_roi_pct(profit=5.0, landed_cost=0.0) == 0.0


def test_calculate_profitability_runs_the_full_chain():
    result = calculate_profitability(
        unit_price=4.0, shipping_cost=800.0, moq=1000, selling_price=20.0, fee_pct=18.0
    )
    assert result.landed_cost == 4.8
    assert result.marketplace_fee == 3.6
    assert result.profit == 11.6
    assert result.margin_pct == 58.0
    assert result.roi_pct == pytest.approx(241.67, abs=0.01)


def test_calculate_profitability_reports_a_loss_correctly():
    result = calculate_profitability(
        unit_price=15.0, shipping_cost=200.0, moq=50, selling_price=16.0, fee_pct=18.0
    )
    assert result.profit < 0
    assert result.margin_pct < 0
    assert result.roi_pct < 0


@pytest.mark.parametrize(
    "margin_pct, roi_pct, expected",
    [
        (25.0, 60.0, Decision.BUY_TEST),  # clears both BUY thresholds
        (20.0, 50.0, Decision.BUY_TEST),  # exactly at the BUY thresholds
        (19.9, 60.0, Decision.WATCH),  # margin just misses BUY, still clears WATCH
        (25.0, 49.9, Decision.WATCH),  # roi just misses BUY, still clears WATCH
        (10.0, 25.0, Decision.WATCH),
        (5.0, 10.0, Decision.REJECT),
        (-10.0, -5.0, Decision.REJECT),
    ],
)
def test_determine_decision_thresholds(margin_pct, roi_pct, expected):
    assert determine_decision(margin_pct, roi_pct) == expected


@pytest.mark.parametrize("decision", list(Decision))
def test_build_rationale_reports_the_given_numbers(decision):
    rationale = build_rationale(decision, margin_pct=12.3, roi_pct=45.6, profit=7.89)
    assert "12.3" in rationale
    assert "45.6" in rationale


def test_build_rationale_describes_a_loss_as_a_loss_not_a_bare_negative_number():
    rationale = build_rationale(Decision.REJECT, margin_pct=-10.0, roi_pct=-5.0, profit=-3.5)
    assert "loss" in rationale
    assert "-3.5" not in rationale
    assert "$3.50" in rationale


def test_build_rationale_uses_the_given_currency_symbol_not_a_hardcoded_dollar():
    rationale = build_rationale(
        Decision.BUY_TEST, margin_pct=40.0, roi_pct=120.0, profit=6.8, currency="GBP"
    )
    assert "£6.80" in rationale
    assert "$" not in rationale


def test_build_rationale_falls_back_to_dollar_for_usd():
    rationale = build_rationale(Decision.WATCH, margin_pct=10.0, roi_pct=25.0, profit=2.0)
    assert "$2.00" in rationale
