from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.logging import get_logger
from app.modules.opportunity.query_parsing import parse_search_criteria
from app.modules.opportunity.service import discover_opportunities
from app.modules.profitability.service import evaluate_profitability
from app.modules.runs import repository
from app.modules.runs.models import RunStatus, SearchRun
from app.modules.suppliers.service import source_suppliers

logger = get_logger(__name__)

# Caps how many top-ranked opportunities get sourced and priced per run. Keeps one
# search from fanning out into dozens of supplier-provider calls before there's any
# real provider cost or rate limit to worry about.
MAX_OPPORTUNITIES_TO_EVALUATE = 5


def start_run(db: Session, *, query: str, filters: dict[str, Any] | None = None) -> SearchRun:
    """Creates a `SearchRun` and commits it immediately.

    Committed on its own, ahead of the pipeline in `execute_run`, so the run is
    visible (as PENDING) the moment it's requested rather than only once the whole
    — possibly slow, possibly failing — pipeline finishes.
    """

    run = SearchRun(query_text=query, filters=filters or {}, status=RunStatus.PENDING)
    repository.add_run(db, run)
    db.commit()
    db.refresh(run)
    return run


def execute_run(db: Session, run: SearchRun) -> SearchRun:
    """Runs discovery -> supplier sourcing -> profitability for one run, end to end.

    Each stage's service call adds rows to the session but does not commit — this
    function owns the single transaction boundary for the whole pipeline, so a run's
    results land complete or not at all; a mid-pipeline error rolls back everything
    since `start_run`'s commit and leaves the run marked FAILED with a reason, rather
    than a half-populated opportunity list.
    """

    # Bound for the rest of this pipeline's execution so every log line emitted
    # by the opportunity/suppliers/profitability services and call_logger below
    # — not just the two explicit run_id= calls in this function — carries it,
    # letting `run_id` correlate a run's logs the same way `request_id` does for
    # a single HTTP request.
    structlog.contextvars.bind_contextvars(run_id=str(run.id))

    run.status = RunStatus.RUNNING
    # Parsed once here (rather than left to `discover_opportunities` to parse on
    # its own) and written back onto the run, so what the dashboard displays as
    # "how this search was understood" is exactly what generation used — not a
    # second, possibly-different parse of the same text.
    criteria = parse_search_criteria(run.query_text, run.filters)
    run.filters = {**(run.filters or {}), "parsed_criteria": criteria.to_dict()}
    db.add(run)
    db.commit()

    try:
        opportunities = discover_opportunities(
            db, run_id=run.id, query=run.query_text, filters=run.filters
        )
        # Flush so each opportunity's id (a client-side default applied at flush, not
        # at construction) is populated before the loop below logs it — the FK links
        # below don't depend on this, since they're set via relationship assignment
        # and let SQLAlchemy's unit-of-work order the inserts correctly on its own.
        db.flush()
        top_opportunities = opportunities[:MAX_OPPORTUNITIES_TO_EVALUATE]

        for opportunity in top_opportunities:
            offers = source_suppliers(db, run_id=run.id, opportunity=opportunity)
            if offers:
                evaluate_profitability(db, opportunity=opportunity, supplier_offers=offers)

        run.status = RunStatus.COMPLETE
        run.completed_at = utcnow()
        db.commit()
        db.refresh(run)
    except Exception as exc:
        db.rollback()
        run.status = RunStatus.FAILED
        run.error_message = str(exc)[:1000]
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.error("run_failed", run_id=str(run.id), error=str(exc))
        return run

    logger.info("run_completed", run_id=str(run.id), opportunity_count=len(top_opportunities))
    return run


def run_search(db: Session, *, query: str, filters: dict[str, Any] | None = None) -> SearchRun:
    """Convenience entry point for the MVP's synchronous flow: create the run, then
    execute it in the same request. `start_run`/`execute_run` stay split so a future
    move to a background job queue only has to change what calls them, not the
    pipeline itself.
    """

    run = start_run(db, query=query, filters=filters)
    return execute_run(db, run)
