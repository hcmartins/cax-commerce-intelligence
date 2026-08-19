import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country: str | None
    website: str | None
    contact_email: str | None
    contact_phone: str | None
    source: str


class SupplierOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_opportunity_id: uuid.UUID
    supplier: SupplierOut
    unit_price: float
    currency: str
    moq: int
    lead_time_days: int | None
    shipping_method: str | None
    shipping_cost: float | None
    notes: str | None
    created_at: datetime
