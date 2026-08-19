from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logging import get_logger

logger = get_logger(__name__)


class NotFoundError(Exception):
    """Raised by a route handler when a requested resource doesn't exist."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    """Raised by a route handler when a request is well-formed but can't be
    performed given the resource's current state (e.g. approving an opportunity
    that hasn't finished profitability yet).
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _error_response(status_code: int, message: str, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"message": message, **extra}})


def register_exception_handlers(app: FastAPI) -> None:
    """Wires every route's failure modes to one consistent `{"error": {...}}` shape,
    so API clients (the dashboard included) never have to special-case a raw
    traceback or FastAPI's default validation-error format.
    """

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return _error_response(status.HTTP_404_NOT_FOUND, exc.message)

    @app.exception_handler(ConflictError)
    async def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return _error_response(status.HTTP_409_CONFLICT, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Validation failed", details=exc.errors()
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", path=str(request.url), error=str(exc))
        return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")
