import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Supplier(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supplier"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    offers: Mapped[list["SupplierOffer"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )


class SupplierOffer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A supplier's quoted terms for one specific product opportunity."""

    __tablename__ = "supplier_offer"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False
    )
    product_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )

    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    moq: Mapped[int] = mapped_column(Integer, default=1)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    shipping_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="offers")
    opportunity: Mapped["ProductOpportunity"] = relationship(  # noqa: F821
        back_populates="supplier_offers"
    )
    profitability_calculations: Mapped[list["ProfitabilityCalculation"]] = relationship(  # noqa: F821
        back_populates="supplier_offer", cascade="all, delete-orphan"
    )
