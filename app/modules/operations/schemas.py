import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.operations.models import ApprovalStatus


class OperationsApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_opportunity_id: uuid.UUID
    status: ApprovalStatus
    external_reference: str | None
    error_message: str | None
    created_at: datetime
