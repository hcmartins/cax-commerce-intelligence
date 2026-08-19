import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProductOpportunity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "product_opportunity"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_run.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    demand_score: Mapped[float] = mapped_column(Float, default=0.0)
    competition_score: Mapped[float] = mapped_column(Float, default=0.0)
    trend_score: Mapped[float] = mapped_column(Float, default=0.0)
    avg_selling_price: Mapped[float] = mapped_column(Float, default=0.0)

    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    raw_evidence: Mapped[dict] = mapped_column(JSONB, default=dict)

    run: Mapped["SearchRun"] = relationship(back_populates="opportunities")  # noqa: F821
    supplier_offers: Mapped[list["SupplierOffer"]] = relationship(  # noqa: F821
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    profitability_calculations: Mapped[list["ProfitabilityCalculation"]] = relationship(  # noqa: F821
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(  # noqa: F821
        back_populates="opportunity", cascade="all, delete-orphan"
    )

    @property
    def best_calculation(self) -> "ProfitabilityCalculation | None":  # noqa: F821
        """The most profitable evaluated supplier offer for this opportunity, if the
        profitability stage has run for it yet — `None` otherwise. "Best" is by raw
        profit/unit; ties aren't expected to matter for the MVP's small offer counts.
        """

        evaluated = [c for c in self.profitability_calculations if c.recommendation is not None]
        if not evaluated:
            return None
        return max(evaluated, key=lambda c: c.profit)

    @property
    def best_offer(self) -> dict | None:
        """A flat summary of `best_calculation` for the API/UI — `None` when this
        opportunity hasn't been through supplier sourcing + profitability yet (the
        pipeline only evaluates the top-ranked opportunities per run, so this is a
        normal, expected state for the rest, not an error).
        """

        calc = self.best_calculation
        if calc is None:
            return None
        return {
            "decision": calc.recommendation.decision.value,
            "margin_pct": calc.margin_pct,
            "roi_pct": calc.roi_pct,
            "profit": calc.profit,
            "landed_cost": calc.landed_cost,
            "selling_price": calc.selling_price,
            "unit_price": calc.supplier_offer.unit_price,
            "currency": calc.currency,
        }

    @property
    def data_quality(self) -> str:
        """Whether this opportunity's evidence came from a real integration or the
        MVP's deterministic mock providers — see requirement to never present
        synthetic data as verified marketplace intelligence.
        """

        return "DEMO" if self.source == "mock" else "LIVE"
