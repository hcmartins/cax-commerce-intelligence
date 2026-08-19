"""Unversioned, unauthenticated infrastructure endpoints — liveness and readiness
probes. Kept outside `app/api/v1` (and outside `settings.api_v1_prefix`) since
these are container/orchestrator contracts, not part of the versioned business
API: `docker-compose.yml`'s healthchecks and any future deployment platform's
probes should never have to track an API version bump.

`/api/v1/health` (see `app/api/v1/health.py`) is kept as-is alongside these for
backward compatibility with the dashboard and existing tests/docs that already
depend on it — it behaves the same as `/ready` below.
"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["system"], include_in_schema=True)


@router.get("/health", summary="Liveness probe")
def liveness() -> JSONResponse:
    """Process is up and able to handle requests. Does **not** touch the database
    — a slow/unreachable DB should surface as a failing `/ready`, not restart a
    perfectly healthy API process.
    """

    return JSONResponse(content={"status": "ok"})


@router.get("/ready", summary="Readiness probe")
def readiness(db: DbSession) -> JSONResponse:
    """Process is up **and** its dependencies (currently: the database) are
    reachable — safe to route traffic to. Used by `docker-compose.yml`'s
    `service_healthy` condition to gate the UI's startup on the API actually
    being able to serve requests, not just having started.
    """

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "unreachable"},
        )
    return JSONResponse(content={"status": "ok", "database": "reachable"})
