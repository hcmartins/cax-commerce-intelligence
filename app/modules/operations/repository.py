import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.operations.models import OperationsApproval


def add_approval(db: Session, approval: OperationsApproval) -> None:
    db.add(approval)


def list_by_opportunity(db: Session, opportunity_id: uuid.UUID) -> list[OperationsApproval]:
    stmt = (
        select(OperationsApproval)
        .where(OperationsApproval.product_opportunity_id == opportunity_id)
        .order_by(OperationsApproval.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
