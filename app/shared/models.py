import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IntegrationCallLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit record of every outbound call to an AI model or external data provider.

    Persisted for every module/provider combination so runs can be replayed,
    debugged, and costed after the fact (MVP persistence requirement).
    """

    __tablename__ = "integration_call_log"

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_run.id", ondelete="SET NULL"), nullable=True
    )
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_category: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)

    request: Mapped[dict] = mapped_column(JSONB, default=dict)
    response: Mapped[dict] = mapped_column(JSONB, default=dict)

    status: Mapped[str] = mapped_column(String(16), default="success")
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
