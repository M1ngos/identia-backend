from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    key_prefix: Mapped[str] = mapped_column(
        String(16),
        unique=True,
        nullable=False,
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    owner_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_api_keys_owner_active", "owner_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, prefix='{self.key_prefix}', owner='{self.owner_id}')>"
