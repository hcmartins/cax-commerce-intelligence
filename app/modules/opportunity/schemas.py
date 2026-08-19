import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BestOfferSummary(BaseModel):
    """The most profitable evaluated supplier offer for an opportunity — present
    once supplier sourcing + profitability have run for it, `None` until then.
    """

    decision: str
    margin_pct: float
    roi_pct: float
    profit: float
    landed_cost: float
    selling_price: float
    unit_price: float
    currency: str


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    title: str
    category: str | None
    source: str
    currency: str
    demand_score: float
    competition_score: float
    trend_score: float
    avg_selling_price: float
    overall_score: float
    rank: int | None
    best_offer: BestOfferSummary | None
    data_quality: str
    created_at: datetime


class OpportunityDetail(OpportunityOut):
    raw_evidence: dict
