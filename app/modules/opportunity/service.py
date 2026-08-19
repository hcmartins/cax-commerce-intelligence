import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.integrations.factory import get_search_provider
from app.logging import get_logger
from app.modules.opportunity import repository
from app.modules.opportunity.models import ProductOpportunity
from app.modules.opportunity.query_parsing import get_or_parse_criteria
from app.modules.opportunity.ranking import rank_opportunities
from app.modules.opportunity.validation import find_duplicate_indices, is_valid_product_title
from app.shared.call_logger import log_integration_call

logger = get_logger(__name__)

MODULE_NAME = "opportunity"


def _filter_candidates(candidates: list[dict], query: str) -> list[dict]:
    """Deterministic safety net over whatever the search provider returned: drops
    any candidate whose title reads as an instruction/echo of the query rather
    than a product, and drops near-duplicates within the same batch. Doesn't
    depend on the provider (mock catalog today, potentially an AI-backed one
    later) to have gotten this right on its own — see `validation.py`.
    """

    valid = []
    for candidate in candidates:
        title = candidate.get("title", "")
        ok, reason = is_valid_product_title(title, query)
        if not ok:
            logger.warning("opportunity_title_rejected", title=title, reason=reason)
            continue
        valid.append(candidate)

    duplicate_indices = find_duplicate_indices([c["title"] for c in valid])
    if duplicate_indices:
        logger.warning(
            "opportunity_duplicates_dropped",
            titles=[valid[i]["title"] for i in duplicate_indices],
        )
    return [c for i, c in enumerate(valid) if i not in duplicate_indices]


def discover_opportunities(
    db: Session, *, run_id: uuid.UUID, query: str, filters: dict[str, Any] | None = None
) -> list[ProductOpportunity]:
    """Finds, scores and ranks candidate products for a search run.

    Persists the resulting `ProductOpportunity` rows (added to the session; the
    caller/orchestrator is responsible for committing).
    """

    criteria = get_or_parse_criteria(query, filters)
    provider = get_search_provider()
    result = provider.search_products(query, criteria.to_provider_filters())
    log_integration_call(db, run_id=run_id, module=MODULE_NAME, provider_category="search", result=result)

    candidates = _filter_candidates(result.data, query)

    opportunities = [
        ProductOpportunity(
            run_id=run_id,
            title=candidate["title"],
            category=candidate.get("category"),
            source=provider.name,
            currency=candidate.get("currency") or criteria.currency,
            demand_score=candidate.get("demand_score", 0.0),
            competition_score=candidate.get("competition_score", 0.0),
            trend_score=candidate.get("trend_score", 0.0),
            avg_selling_price=candidate.get("avg_selling_price", 0.0),
            raw_evidence=candidate.get("evidence", {}),
        )
        for candidate in candidates
    ]

    rank_opportunities(opportunities)
    repository.add_opportunities(db, opportunities)

    logger.info("opportunities_discovered", run_id=str(run_id), count=len(opportunities))
    return opportunities
