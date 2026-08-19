from sqlalchemy.orm import Session

from app.integrations.factory import get_operations_provider
from app.logging import get_logger
from app.modules.opportunity.models import ProductOpportunity
from app.modules.operations import repository
from app.modules.operations.models import ApprovalStatus, OperationsApproval
from app.shared.call_logger import log_integration_call

logger = get_logger(__name__)

MODULE_NAME = "operations"


class NotReadyForApprovalError(Exception):
    """Raised when an opportunity hasn't completed supplier sourcing and
    profitability yet — there's no commercial case to approve without those.
    """


def _build_payload(opportunity: ProductOpportunity) -> dict:
    best_offer = opportunity.best_offer
    return {
        "opportunity_id": str(opportunity.id),
        "title": opportunity.title,
        "category": opportunity.category,
        "currency": opportunity.currency,
        "decision": best_offer["decision"],
        "unit_price": best_offer["unit_price"],
        "landed_cost": best_offer["landed_cost"],
        "selling_price": best_offer["selling_price"],
        "margin_pct": best_offer["margin_pct"],
        "roi_pct": best_offer["roi_pct"],
    }


def approve_for_operations(db: Session, *, opportunity: ProductOpportunity) -> OperationsApproval:
    """Submits an opportunity that has completed supplier sourcing + profitability
    to the (separate) Commerce Operations platform for procurement/inventory/
    listing. Every attempt — successful or not — is persisted, so a failure never
    loses the fact that approval was requested; calling this again is how a
    failed attempt gets retried.

    Standalone action (like `profitability.recalculate`): owns and commits its
    own transaction rather than deferring to an orchestrator.
    """

    if opportunity.best_offer is None:
        raise NotReadyForApprovalError(
            "This opportunity hasn't completed supplier sourcing and profitability yet."
        )

    payload = _build_payload(opportunity)
    provider = get_operations_provider()

    try:
        result = provider.submit_approval(str(opportunity.id), payload)
    except Exception as exc:  # noqa: BLE001 - the whole point: never let this crash the request
        logger.error("operations_approval_provider_error", opportunity_id=str(opportunity.id), error=str(exc))
        approval = OperationsApproval(
            product_opportunity_id=opportunity.id,
            status=ApprovalStatus.FAILED,
            error_message=str(exc)[:1000],
            payload=payload,
        )
        repository.add_approval(db, approval)
        db.commit()
        db.refresh(approval)
        return approval

    log_integration_call(
        db, run_id=None, module=MODULE_NAME, provider_category="operations", result=result
    )

    if result.status == "success":
        approval = OperationsApproval(
            product_opportunity_id=opportunity.id,
            status=ApprovalStatus.SENT,
            external_reference=(result.data or {}).get("external_reference"),
            payload=payload,
        )
    else:
        approval = OperationsApproval(
            product_opportunity_id=opportunity.id,
            status=ApprovalStatus.FAILED,
            error_message=result.error_message,
            payload=payload,
        )

    repository.add_approval(db, approval)
    db.commit()
    db.refresh(approval)

    logger.info(
        "operations_approval_submitted",
        opportunity_id=str(opportunity.id),
        status=approval.status.value,
    )
    return approval
