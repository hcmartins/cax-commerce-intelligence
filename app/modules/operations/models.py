import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class OperationsApproval(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One attempt to hand an approved opportunity off to the separate Commerce
    Operations platform. Every attempt is kept (not overwritten) so a failed
    hand-off can be retried without losing the record that it was ever tried.
    """

    __tablename__ = "operations_approval"

    product_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_opportunity.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status"), default=ApprovalStatus.PENDING, nullable=False
    )
    external_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
