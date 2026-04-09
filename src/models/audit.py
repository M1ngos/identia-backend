from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.user import User


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    extra_data: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[User | None] = relationship(
        "User",
        back_populates="audit_logs",
    )

    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_action", "action"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', success={self.success})>"
