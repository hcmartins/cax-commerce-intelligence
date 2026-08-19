import uuid

from sqlalchemy.orm import Session

from app.integrations.base import ProviderCallResult
from app.logging import get_logger
from app.shared.models import IntegrationCallLog

logger = get_logger(__name__)


def log_integration_call(
    db: Session,
    *,
    run_id: uuid.UUID | None,
    module: str,
    provider_category: str,
    result: ProviderCallResult,
) -> IntegrationCallLog:
    """Persist an audit record for one outbound integration call.

    Added to the session but not committed — callers own the transaction boundary
    (typically the orchestrator commits once per pipeline stage).
    """

    entry = IntegrationCallLog(
        run_id=run_id,
        module=module,
        provider_category=provider_category,
        provider_name=result.provider_name,
        request=result.request,
        response=result.response,
        status=result.status,
        tokens_used=result.tokens_used,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
        error_message=result.error_message,
    )
    db.add(entry)

    log = logger.warning if result.status != "success" else logger.info
    log(
        "integration_call",
        module=module,
        provider_category=provider_category,
        provider_name=result.provider_name,
        status=result.status,
        latency_ms=result.latency_ms,
    )
    return entry
