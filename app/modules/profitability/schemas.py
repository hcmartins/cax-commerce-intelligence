import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.profitability.models import Decision


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    decision: Decision
    rationale: str
    confidence: float
    created_at: datetime


class ProfitabilityCalculationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_opportunity_id: uuid.UUID
    supplier_offer_id: uuid.UUID
    landed_cost: float
    selling_price: float
    marketplace_fee: float
    shipping_cost: float
    other_costs: float
    profit: float
    margin_pct: float
    roi_pct: float
    currency: str
    assumptions: dict
    recommendation: RecommendationOut | None
    created_at: datetime


class ProfitabilityRecalculateRequest(BaseModel):
    """Optional overrides for a what-if recalculation; unset fields fall back to the
    opportunity's discovered price and the app's configured default fee percentages.
    """

    supplier_offer_id: uuid.UUID
    selling_price: float | None = Field(default=None, gt=0)
    marketplace_fee_pct: float | None = Field(default=None, ge=0)
    payment_fee_pct: float | None = Field(default=None, ge=0)
    other_costs: float = Field(default=0.0, ge=0)
