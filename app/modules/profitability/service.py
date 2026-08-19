from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging import get_logger
from app.modules.opportunity.models import ProductOpportunity
from app.modules.profitability import repository
from app.modules.profitability.calculator import (
    ProfitabilityResult,
    build_rationale,
    calculate_profitability,
    determine_decision,
)
from app.modules.profitability.models import ProfitabilityCalculation, Recommendation
from app.modules.suppliers.models import SupplierOffer

logger = get_logger(__name__)


def _build_calculation_and_recommendation(
    *,
    opportunity: ProductOpportunity,
    offer: SupplierOffer,
    result: ProfitabilityResult,
    assumptions: dict,
) -> tuple[ProfitabilityCalculation, Recommendation]:
    calculation = ProfitabilityCalculation(
        opportunity=opportunity,
        supplier_offer=offer,
        landed_cost=result.landed_cost,
        selling_price=result.selling_price,
        marketplace_fee=result.marketplace_fee,
        shipping_cost=result.shipping_cost,
        other_costs=result.other_costs,
        profit=result.profit,
        margin_pct=result.margin_pct,
        roi_pct=result.roi_pct,
        currency=offer.currency,
        assumptions=assumptions,
    )

    decision = determine_decision(result.margin_pct, result.roi_pct)
    recommendation = Recommendation(
        opportunity=opportunity,
        profitability_calculation=calculation,
        decision=decision,
        rationale=build_rationale(
            decision, result.margin_pct, result.roi_pct, result.profit, currency=offer.currency
        ),
    )
    return calculation, recommendation


def evaluate_profitability(
    db: Session,
    *,
    opportunity: ProductOpportunity,
    supplier_offers: list[SupplierOffer],
) -> list[ProfitabilityCalculation]:
    """Computes profitability and a recommendation for each candidate supplier offer,
    using the opportunity's discovered market price and the configured default fees.

    Pure internal computation — unlike `opportunity`/`suppliers`, this module calls no
    external provider, so there's no integration call to log. Persists the resulting
    `ProfitabilityCalculation` and `Recommendation` rows, added to the session; the
    caller/orchestrator is responsible for committing.
    """

    settings = get_settings()
    fee_pct = settings.default_marketplace_fee_pct + settings.default_payment_fee_pct

    calculations = []
    recommendations = []
    for offer in supplier_offers:
        result = calculate_profitability(
            unit_price=offer.unit_price,
            shipping_cost=offer.shipping_cost or 0.0,
            moq=offer.moq,
            selling_price=opportunity.avg_selling_price,
            fee_pct=fee_pct,
        )
        calculation, recommendation = _build_calculation_and_recommendation(
            opportunity=opportunity,
            offer=offer,
            result=result,
            assumptions={
                "marketplace_fee_pct": settings.default_marketplace_fee_pct,
                "payment_fee_pct": settings.default_payment_fee_pct,
                "selling_price_source": "opportunity.avg_selling_price",
            },
        )
        calculations.append(calculation)
        recommendations.append(recommendation)

    repository.add_calculations(db, calculations)
    repository.add_recommendations(db, recommendations)

    logger.info(
        "profitability_evaluated", opportunity_id=str(opportunity.id), count=len(calculations)
    )
    return calculations


def recalculate(
    db: Session,
    *,
    opportunity: ProductOpportunity,
    offer: SupplierOffer,
    selling_price: float | None = None,
    marketplace_fee_pct: float | None = None,
    payment_fee_pct: float | None = None,
    other_costs: float = 0.0,
) -> ProfitabilityCalculation:
    """Recomputes profitability for one offer with optionally overridden assumptions.

    Falls back to the opportunity's discovered market price and the configured
    default fee percentages wherever an override isn't supplied. Writes a new
    calculation + recommendation rather than mutating an existing one, so the
    dashboard can let a user try "what if" numbers without losing the original.
    Unlike `evaluate_profitability`, this is a standalone action (typically called
    directly from an API route rather than the run orchestrator), so it owns and
    commits its own transaction.
    """

    settings = get_settings()
    resolved_selling_price = (
        selling_price if selling_price is not None else opportunity.avg_selling_price
    )
    resolved_marketplace_fee_pct = (
        marketplace_fee_pct
        if marketplace_fee_pct is not None
        else settings.default_marketplace_fee_pct
    )
    resolved_payment_fee_pct = (
        payment_fee_pct if payment_fee_pct is not None else settings.default_payment_fee_pct
    )

    result = calculate_profitability(
        unit_price=offer.unit_price,
        shipping_cost=offer.shipping_cost or 0.0,
        moq=offer.moq,
        selling_price=resolved_selling_price,
        fee_pct=resolved_marketplace_fee_pct + resolved_payment_fee_pct,
        other_costs=other_costs,
    )
    calculation, recommendation = _build_calculation_and_recommendation(
        opportunity=opportunity,
        offer=offer,
        result=result,
        assumptions={
            "marketplace_fee_pct": resolved_marketplace_fee_pct,
            "payment_fee_pct": resolved_payment_fee_pct,
            "other_costs": other_costs,
            "selling_price_source": "override" if selling_price is not None else "opportunity.avg_selling_price",
        },
    )

    repository.add_calculations(db, [calculation])
    repository.add_recommendations(db, [recommendation])
    db.commit()
    db.refresh(calculation)

    logger.info(
        "profitability_recalculated", opportunity_id=str(opportunity.id), offer_id=str(offer.id)
    )
    return calculation
