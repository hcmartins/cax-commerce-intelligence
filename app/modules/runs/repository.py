import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.runs.models import SearchRun


def add_run(db: Session, run: SearchRun) -> None:
    db.add(run)


def get_by_id(db: Session, run_id: uuid.UUID) -> SearchRun | None:
    return db.get(SearchRun, run_id)


def list_runs(db: Session, *, limit: int = 50, offset: int = 0) -> list[SearchRun]:
    stmt = select(SearchRun).order_by(SearchRun.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())
