import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.runs.models import RunStatus


class SearchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query_text: str
    filters: dict
    status: RunStatus
    error_message: str | None
    completed_at: datetime | None
    created_at: datetime
