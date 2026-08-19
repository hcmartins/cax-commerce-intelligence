import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.suppliers.models import Supplier, SupplierOffer


def get_or_create_supplier(
    db: Session,
    *,
    name: str,
    source: str,
    country: str | None = None,
    website: str | None = None,
    contact_email: str | None = None,
    contact_phone: str | None = None,
) -> Supplier:
    """Looks up a supplier by (name, source), creating it if this is the first time
    that provider has surfaced it.

    Keeps the supplier directory de-duplicated across runs instead of growing a new
    row every time a provider resurfaces the same company. There's no DB-level
    uniqueness constraint on (name, source) — a real provider could plausibly return
    the same company spelled two different ways — so the lookup takes the first match
    rather than demanding exactly one, and stays a graceful find-or-create rather than
    a strict integrity check.
    """

    stmt = select(Supplier).where(Supplier.name == name, Supplier.source == source).limit(1)
    existing = db.execute(stmt).scalars().first()
    if existing is not None:
        return existing

    supplier = Supplier(
        name=name,
        source=source,
        country=country,
        website=website,
        contact_email=contact_email,
        contact_phone=contact_phone,
    )
    db.add(supplier)
    # Flushed (not committed) so a second candidate with the same name later in this
    # same batch sees it via the query above instead of racing it into a duplicate row
    # — the session doesn't autoflush, so without this the SELECT can't see an insert
    # that's only pending in this same transaction.
    db.flush()
    return supplier


def add_offers(db: Session, offers: list[SupplierOffer]) -> None:
    db.add_all(offers)


def list_by_opportunity(db: Session, opportunity_id: uuid.UUID) -> list[SupplierOffer]:
    stmt = (
        select(SupplierOffer)
        .where(SupplierOffer.product_opportunity_id == opportunity_id)
        .options(selectinload(SupplierOffer.supplier))
        .order_by(SupplierOffer.unit_price.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_by_id(db: Session, offer_id: uuid.UUID) -> SupplierOffer | None:
    return db.get(SupplierOffer, offer_id)
