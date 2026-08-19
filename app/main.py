from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.middleware import request_context_middleware
from app.api.system import router as system_router
from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.db import models_registry  # noqa: F401  (registers every model with Base.metadata)
from app.logging import configure_logging

settings = get_settings()
configure_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Discovers profitable products, sources suppliers, and scores landed-cost "
        "profitability into a BUY_TEST / WATCH / REJECT recommendation."
    ),
)

app.middleware("http")(request_context_middleware)

register_exception_handlers(app)
app.include_router(system_router)
app.include_router(v1_router, prefix=settings.api_v1_prefix)
