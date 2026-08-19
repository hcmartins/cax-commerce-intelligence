import uuid

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.api.errors import ConflictError, NotFoundError
from app.modules.operations import repository as operations_repository
from app.modules.operations import service as operations_service
from app.modules.operations.schemas import OperationsApprovalOut
from app.modules.operations.service import NotReadyForApprovalError
from app.modules.opportunity import repository as opportunity_repository
from app.modules.opportunity.models import ProductOpportunity
from app.modules.opportunity.schemas import OpportunityDetail
from app.modules.profitability import repository as profitability_repository
from app.modules.profitability import service as profitability_service
from app.modules.profitability.schemas import ProfitabilityCalculationOut, ProfitabilityRecalculateRequest
from app.modules.suppliers import repository as suppliers_repository
from app.modules.suppliers.schemas import SupplierOfferOut

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _get_opportunity_or_404(db: DbSession, opportunity_id: uuid.UUID) -> ProductOpportunity:
    opportunity = opportunity_repository.get_by_id(db, opportunity_id)
    if opportunity is None:
        raise NotFoundError(f"Opportunity {opportunity_id} not found")
    return opportunity


@router.get("/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(opportunity_id: uuid.UUID, db: DbSession) -> OpportunityDetail:
    return _get_opportunity_or_404(db, opportunity_id)


@router.get("/{opportunity_id}/suppliers", response_model=list[SupplierOfferOut])
def list_opportunity_suppliers(opportunity_id: uuid.UUID, db: DbSession) -> list[SupplierOfferOut]:
    _get_opportunity_or_404(db, opportunity_id)
    return suppliers_repository.list_by_opportunity(db, opportunity_id)


@router.get("/{opportunity_id}/profitability", response_model=list[ProfitabilityCalculationOut])
def list_opportunity_profitability(
    opportunity_id: uuid.UUID, db: DbSession
) -> list[ProfitabilityCalculationOut]:
    _get_opportunity_or_404(db, opportunity_id)
    return profitability_repository.list_by_opportunity(db, opportunity_id)


@router.post(
    "/{opportunity_id}/profitability:recalculate",
    response_model=ProfitabilityCalculationOut,
    status_code=status.HTTP_201_CREATED,
)
def recalculate_opportunity_profitability(
    opportunity_id: uuid.UUID, payload: ProfitabilityRecalculateRequest, db: DbSession
) -> ProfitabilityCalculationOut:
    opportunity = _get_opportunity_or_404(db, opportunity_id)

    offer = suppliers_repository.get_by_id(db, payload.supplier_offer_id)
    if offer is None or offer.product_opportunity_id != opportunity_id:
        raise NotFoundError(
            f"Supplier offer {payload.supplier_offer_id} not found for opportunity {opportunity_id}"
        )

    return profitability_service.recalculate(
        db,
        opportunity=opportunity,
        offer=offer,
        selling_price=payload.selling_price,
        marketplace_fee_pct=payload.marketplace_fee_pct,
        payment_fee_pct=payload.payment_fee_pct,
        other_costs=payload.other_costs,
    )


@router.post(
    "/{opportunity_id}/approve",
    response_model=OperationsApprovalOut,
    status_code=status.HTTP_201_CREATED,
)
def approve_opportunity_for_operations(
    opportunity_id: uuid.UUID, db: DbSession
) -> OperationsApprovalOut:
    """Hands an opportunity that has completed supplier sourcing + profitability to
    the (separate) Commerce Operations platform. A `201` here means the *attempt*
    was recorded — check `status`: `SENT` succeeded, `FAILED` didn't (the response
    still includes why), and calling this again is how a failed attempt is retried.
    """

    opportunity = _get_opportunity_or_404(db, opportunity_id)
    try:
        return operations_service.approve_for_operations(db, opportunity=opportunity)
    except NotReadyForApprovalError as exc:
        raise ConflictError(str(exc)) from exc


@router.get("/{opportunity_id}/approvals", response_model=list[OperationsApprovalOut])
def list_opportunity_approvals(opportunity_id: uuid.UUID, db: DbSession) -> list[OperationsApprovalOut]:
    _get_opportunity_or_404(db, opportunity_id)
    return operations_repository.list_by_opportunity(db, opportunity_id)
