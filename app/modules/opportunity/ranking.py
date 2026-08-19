"""Scoring and ranking logic for product opportunities.

Deliberately simple and rule-based for the MVP (a weighted average of the three
evidence signals) rather than a learned model — see ARCHITECTURE decision log.
"""

from app.modules.opportunity.models import ProductOpportunity

DEMAND_WEIGHT = 0.4
TREND_WEIGHT = 0.3
COMPETITION_WEIGHT = 0.3  # applied to (100 - competition_score): lower competition is better


def compute_overall_score(demand_score: float, competition_score: float, trend_score: float) -> float:
    inverted_competition = 100 - competition_score
    score = (
        demand_score * DEMAND_WEIGHT
        + trend_score * TREND_WEIGHT
        + inverted_competition * COMPETITION_WEIGHT
    )
    return round(max(0.0, min(100.0, score)), 2)


def rank_opportunities(opportunities: list[ProductOpportunity]) -> list[ProductOpportunity]:
    """Assigns `overall_score` and `rank` in place, ordered best-first."""

    for opp in opportunities:
        opp.overall_score = compute_overall_score(
            opp.demand_score, opp.competition_score, opp.trend_score
        )

    opportunities.sort(key=lambda o: o.overall_score, reverse=True)
    for index, opp in enumerate(opportunities, start=1):
        opp.rank = index

    return opportunities
