"""Request-scoped structured logging context: every log line emitted while
handling a request — across routers, services, and `call_logger`'s integration
audit trail — automatically carries the same `request_id`, without threading it
through every function signature.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response

from app.logging import get_logger

REQUEST_ID_HEADER = "X-Request-ID"

access_logger = get_logger("http.access")


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        access_logger.error("request_failed", duration_ms=duration_ms)
        raise

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers[REQUEST_ID_HEADER] = request_id
    access_logger.info(
        "request_completed", status_code=response.status_code, duration_ms=duration_ms
    )
    return response
