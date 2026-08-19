import uuid

from sqlalchemy.orm import Session

from app.integrations.factory import get_supplier_provider
from app.logging import get_logger
from app.modules.opportunity.models import ProductOpportunity
from app.modules.suppliers import repository
from app.modules.suppliers.models import SupplierOffer
from app.shared.call_logger import log_integration_call

logger = get_logger(__name__)

MODULE_NAME = "suppliers"


def source_suppliers(
    db: Session, *, run_id: uuid.UUID, opportunity: ProductOpportunity
) -> list[SupplierOffer]:
    """Finds and persists candidate supplier offers for one shortlisted opportunity.

    Persists the resulting `Supplier` (deduplicated) and `SupplierOffer` rows, added
    to the session; the caller/orchestrator is responsible for committing.
    """

    provider = get_supplier_provider()
    result = provider.find_suppliers(
        opportunity.title,
        opportunity.category,
        opportunity.avg_selling_price,
        currency=opportunity.currency,
    )
    log_integration_call(
        db, run_id=run_id, module=MODULE_NAME, provider_category="suppliers", result=result
    )

    offers = []
    for candidate in result.data:
        supplier = repository.get_or_create_supplier(
            db,
            name=candidate["name"],
            source=provider.name,
            country=candidate.get("country"),
            website=candidate.get("website"),
            contact_email=candidate.get("contact_email"),
            contact_phone=candidate.get("contact_phone"),
        )
        offer = SupplierOffer(
            supplier=supplier,
            opportunity=opportunity,
            unit_price=candidate["unit_price"],
            currency=candidate.get("currency") or opportunity.currency,
            moq=candidate.get("moq", 1),
            lead_time_days=candidate.get("lead_time_days"),
            shipping_method=candidate.get("shipping_method"),
            shipping_cost=candidate.get("shipping_cost"),
            notes=candidate.get("notes"),
        )
        # Added immediately rather than batched after the loop: `get_or_create_supplier`
        # flushes when it creates a new supplier, and flush() resolves every relationship
        # it can see — an offer still sitting outside the session at that point (but
        # already linked in memory via `opportunity=`/`supplier=`) triggers a SQLAlchemy
        # cascade warning instead of being persisted.
        db.add(offer)
        offers.append(offer)

    logger.info("suppliers_sourced", opportunity_id=str(opportunity.id), count=len(offers))
    return offers
