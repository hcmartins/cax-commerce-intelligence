import enum
from datetime import datetime

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class SearchRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "search_run"

    query_text: Mapped[str] = mapped_column(String(512), nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"), default=RunStatus.PENDING, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    opportunities: Mapped[list["ProductOpportunity"]] = relationship(  # noqa: F821
        back_populates="run", cascade="all, delete-orphan"
    )
