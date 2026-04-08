from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.user import User


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    biometric_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    embedding_vector: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )
    embedding_dimension: Mapped[int] = mapped_column(
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="embeddings",
    )

    __table_args__ = (
        Index("ix_embeddings_user_id", "user_id"),
        Index("ix_embeddings_user_type_active", "user_id", "biometric_type", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Embedding(id={self.id}, type='{self.biometric_type}', user_id={self.user_id})>"
