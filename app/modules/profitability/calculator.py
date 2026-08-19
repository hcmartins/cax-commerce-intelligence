"""Pure profitability arithmetic and decision thresholds for the MVP.

No I/O, no ORM — every function takes primitives and returns primitives, so the
money math is unit-testable without a database or a running app. See
`opportunity/ranking.py` for the same pattern applied to opportunity scoring.
"""

from dataclasses import dataclass

from app.modules.profitability.models import Decision

# Decision thresholds — deliberately simple fixed cutoffs for the MVP rather than a
# learned model. Revisit once there's enough completed-run outcome data to tune them.
MIN_MARGIN_PCT_BUY = 20.0
MIN_ROI_PCT_BUY = 50.0
MIN_MARGIN_PCT_WATCH = 8.0
MIN_ROI_PCT_WATCH = 20.0


@dataclass
class ProfitabilityResult:
    landed_cost: float
    selling_price: float
    marketplace_fee: float
    shipping_cost: float
    other_costs: float
    profit: float
    margin_pct: float
    roi_pct: float


def compute_landed_cost(
    unit_price: float, shipping_cost: float, moq: int, other_costs: float = 0.0
) -> float:
    """Cost to land one unit, assuming an order of `moq` units with shipping split evenly.

    `shipping_cost` on a supplier offer is a per-shipment quote, not per-unit — so it
    only becomes part of a single unit's cost once spread across the order quantity.
    """

    shipping_per_unit = (shipping_cost or 0.0) / moq if moq else 0.0
    return round(unit_price + shipping_per_unit + other_costs, 2)


def compute_marketplace_fee(selling_price: float, fee_pct: float) -> float:
    return round(selling_price * (fee_pct / 100), 2)


def compute_profit(selling_price: float, landed_cost: float, marketplace_fee: float) -> float:
    return round(selling_price - landed_cost - marketplace_fee, 2)


def compute_margin_pct(profit: float, selling_price: float) -> float:
    if selling_price <= 0:
        return 0.0
    return round((profit / selling_price) * 100, 2)


def compute_roi_pct(profit: float, landed_cost: float) -> float:
    if landed_cost <= 0:
        return 0.0
    return round((profit / landed_cost) * 100, 2)


def calculate_profitability(
    *,
    unit_price: float,
    shipping_cost: float,
    moq: int,
    selling_price: float,
    fee_pct: float,
    other_costs: float = 0.0,
) -> ProfitabilityResult:
    """Runs the full landed-cost -> profit -> margin/ROI chain for one supplier offer."""

    landed_cost = compute_landed_cost(unit_price, shipping_cost, moq, other_costs)
    marketplace_fee = compute_marketplace_fee(selling_price, fee_pct)
    profit = compute_profit(selling_price, landed_cost, marketplace_fee)

    return ProfitabilityResult(
        landed_cost=landed_cost,
        selling_price=selling_price,
        marketplace_fee=marketplace_fee,
        shipping_cost=shipping_cost or 0.0,
        other_costs=other_costs,
        profit=profit,
        margin_pct=compute_margin_pct(profit, selling_price),
        roi_pct=compute_roi_pct(profit, landed_cost),
    )


def determine_decision(margin_pct: float, roi_pct: float) -> Decision:
    """Deterministic BUY_TEST / WATCH / REJECT rule from margin and ROI.

    Both signals must clear a threshold together — a high margin funded by a tiny,
    high-risk order (poor ROI) shouldn't read as a clean buy, and vice versa.
    """

    if margin_pct >= MIN_MARGIN_PCT_BUY and roi_pct >= MIN_ROI_PCT_BUY:
        return Decision.BUY_TEST
    if margin_pct >= MIN_MARGIN_PCT_WATCH and roi_pct >= MIN_ROI_PCT_WATCH:
        return Decision.WATCH
    return Decision.REJECT


_CURRENCY_SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€"}


def _format_money(value: float, currency: str) -> str:
    symbol = _CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    return f"{symbol}{value:.2f}"


def build_rationale(
    decision: Decision, margin_pct: float, roi_pct: float, profit: float, currency: str = "USD"
) -> str:
    """Deterministic, human-readable explanation of a decision.

    Rule-based for the MVP so the decision path stays predictable and free to run.
    An AI provider can later be swapped in behind this same call site to phrase the
    explanation more richly without changing what data drives the decision itself.
    """

    profit_desc = (
        f"{_format_money(profit, currency)} profit"
        if profit >= 0
        else f"a {_format_money(-profit, currency)} loss"
    )
    if decision == Decision.BUY_TEST:
        return (
            f"Strong margin ({margin_pct:.1f}%) and ROI ({roi_pct:.1f}%) at {profit_desc} per "
            "unit — worth a small test order."
        )
    if decision == Decision.WATCH:
        return (
            f"Modest margin ({margin_pct:.1f}%) and ROI ({roi_pct:.1f}%) at {profit_desc} per "
            "unit — not yet compelling, keep monitoring price and demand."
        )
    return (
        f"Margin ({margin_pct:.1f}%) and/or ROI ({roi_pct:.1f}%) too thin at {profit_desc} per "
        "unit to justify sourcing."
    )
