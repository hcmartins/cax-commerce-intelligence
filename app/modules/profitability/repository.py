import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.profitability.models import ProfitabilityCalculation, Recommendation


def add_calculations(db: Session, calculations: list[ProfitabilityCalculation]) -> None:
    db.add_all(calculations)


def add_recommendations(db: Session, recommendations: list[Recommendation]) -> None:
    db.add_all(recommendations)


def list_by_opportunity(db: Session, opportunity_id: uuid.UUID) -> list[ProfitabilityCalculation]:
    stmt = (
        select(ProfitabilityCalculation)
        .where(ProfitabilityCalculation.product_opportunity_id == opportunity_id)
        .options(selectinload(ProfitabilityCalculation.recommendation))
        .order_by(ProfitabilityCalculation.profit.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_by_id(db: Session, calculation_id: uuid.UUID) -> ProfitabilityCalculation | None:
    return db.get(ProfitabilityCalculation, calculation_id)
