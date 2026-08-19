import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Decision(str, enum.Enum):
    BUY_TEST = "BUY_TEST"
    WATCH = "WATCH"
    REJECT = "REJECT"


class ProfitabilityCalculation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profitability_calculation"

    product_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )
    supplier_offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_offer.id", ondelete="CASCADE"), nullable=False
    )

    landed_cost: Mapped[float] = mapped_column(Float, nullable=False)
    selling_price: Mapped[float] = mapped_column(Float, nullable=False)
    marketplace_fee: Mapped[float] = mapped_column(Float, nullable=False)
    shipping_cost: Mapped[float] = mapped_column(Float, default=0.0)
    other_costs: Mapped[float] = mapped_column(Float, default=0.0)
    # The currency every money field on this row is denominated in — inherited
    # from the supplier offer's currency, which itself inherits from the
    # opportunity's. No FX conversion happens anywhere in the MVP: a calculation
    # is only meaningful when landed cost and selling price share one currency.
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    profit: Mapped[float] = mapped_column(Float, nullable=False)
    margin_pct: Mapped[float] = mapped_column(Float, nullable=False)
    roi_pct: Mapped[float] = mapped_column(Float, nullable=False)

    assumptions: Mapped[dict] = mapped_column(JSONB, default=dict)

    opportunity: Mapped["ProductOpportunity"] = relationship(  # noqa: F821
        back_populates="profitability_calculations"
    )
    supplier_offer: Mapped["SupplierOffer"] = relationship(  # noqa: F821
        back_populates="profitability_calculations"
    )
    recommendation: Mapped["Recommendation"] = relationship(
        back_populates="profitability_calculation", uselist=False, cascade="all, delete-orphan"
    )


class Recommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "recommendation"

    product_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )
    profitability_calculation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profitability_calculation.id", ondelete="CASCADE"),
        nullable=False,
    )

    decision: Mapped[Decision] = mapped_column(Enum(Decision, name="decision"), nullable=False)
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    opportunity: Mapped["ProductOpportunity"] = relationship(  # noqa: F821
        back_populates="recommendations"
    )
    profitability_calculation: Mapped["ProfitabilityCalculation"] = relationship(
        back_populates="recommendation"
    )
