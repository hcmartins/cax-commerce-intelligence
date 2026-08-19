import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.opportunity.models import ProductOpportunity


def _with_best_offer(stmt):
    """Eager-loads everything `ProductOpportunity.best_offer` needs (recommendation
    + the calculation's supplier offer) in two extra queries total, regardless of
    how many opportunities are returned — not one lazy-load per relationship per
    opportunity. Built lazily (not at module import time) so referencing
    `ProfitabilityCalculation` here doesn't force SQLAlchemy to resolve every
    mapper's string-based relationships before `app.db.models_registry` has
    necessarily imported all of them yet.
    """

    from app.modules.profitability.models import ProfitabilityCalculation

    return stmt.options(
        selectinload(ProductOpportunity.profitability_calculations).selectinload(
            ProfitabilityCalculation.recommendation
        ),
        selectinload(ProductOpportunity.profitability_calculations).selectinload(
            ProfitabilityCalculation.supplier_offer
        ),
    )


def add_opportunities(db: Session, opportunities: list[ProductOpportunity]) -> None:
    db.add_all(opportunities)


def get_by_id(db: Session, opportunity_id: uuid.UUID) -> ProductOpportunity | None:
    stmt = _with_best_offer(select(ProductOpportunity).where(ProductOpportunity.id == opportunity_id))
    return db.execute(stmt).scalar_one_or_none()


def list_by_run(db: Session, run_id: uuid.UUID) -> list[ProductOpportunity]:
    stmt = _with_best_offer(
        select(ProductOpportunity)
        .where(ProductOpportunity.run_id == run_id)
        .order_by(ProductOpportunity.rank.asc().nulls_last())
    )
    return list(db.execute(stmt).scalars().all())
