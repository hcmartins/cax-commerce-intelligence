import uuid
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import DbSession, PaginationDep
from app.api.errors import NotFoundError
from app.modules.opportunity import repository as opportunity_repository
from app.modules.opportunity.schemas import OpportunityOut
from app.modules.runs import repository
from app.modules.runs.schemas import SearchRunOut
from app.modules.runs.service import run_search

router = APIRouter(prefix="/runs", tags=["runs"])


class StartRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    filters: dict[str, Any] = Field(default_factory=dict)


def _get_run_or_404(db: DbSession, run_id: uuid.UUID):
    run = repository.get_by_id(db, run_id)
    if run is None:
        raise NotFoundError(f"Run {run_id} not found")
    return run


@router.post("", response_model=SearchRunOut, status_code=status.HTTP_201_CREATED)
def start_run(payload: StartRunRequest, db: DbSession) -> SearchRunOut:
    """Runs the full discovery -> sourcing -> profitability pipeline synchronously
    and returns the finished run — COMPLETE with results, or FAILED with a reason.
    """
    return run_search(db, query=payload.query, filters=payload.filters)


@router.get("", response_model=list[SearchRunOut])
def list_runs(db: DbSession, pagination: PaginationDep) -> list[SearchRunOut]:
    return repository.list_runs(db, limit=pagination.limit, offset=pagination.offset)


@router.get("/{run_id}", response_model=SearchRunOut)
def get_run(run_id: uuid.UUID, db: DbSession) -> SearchRunOut:
    return _get_run_or_404(db, run_id)


@router.get("/{run_id}/opportunities", response_model=list[OpportunityOut])
def list_run_opportunities(run_id: uuid.UUID, db: DbSession) -> list[OpportunityOut]:
    _get_run_or_404(db, run_id)
    return opportunity_repository.list_by_run(db, run_id)
