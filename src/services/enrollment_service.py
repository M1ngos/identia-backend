"""Database-layer service for biometric enrollment operations.

Provides create / read / update / delete operations on User + Embedding rows.
All methods flush but do NOT commit — the FastAPI dependency (get_db) commits
at the end of each request.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    EmbeddingAlreadyExistsError,
    EmbeddingNotFoundError,
    UserNotFoundError,
)
from src.models.embedding import Embedding
from src.models.user import User

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_or_create_user(
    db: AsyncSession,
    external_id: str,
) -> tuple[User, bool]:
    """Return (user, created).  Creates an active User row if absent."""
    result = await db.execute(
        select(User).where(
            User.external_id == external_id,
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is not None:
        return user, False

    user = User(external_id=external_id)
    db.add(user)
    await db.flush()  # populate user.id
    return user, True


async def _get_active_embedding(
    db: AsyncSession,
    user_id: uuid.UUID,
    biometric_type: str,
) -> Embedding | None:
    """Return the active Embedding for user+type, or None."""
    result = await db.execute(
        select(Embedding).where(
            Embedding.user_id == user_id,
            Embedding.biometric_type == biometric_type,
            Embedding.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def enroll_user(
    db: AsyncSession,
    external_id: str,
    biometric_type: str,
    embedding_vector: bytes,
    model_version: str,
    dimension: int,
) -> tuple[User, Embedding]:
    """Enroll a new biometric for a user.

    Creates the User row if it doesn't exist.  Raises if an active embedding
    for the same (user, biometric_type) pair already exists.

    Args:
        db: Active async session.
        external_id: Caller-supplied user identifier.
        biometric_type: e.g. ``"face"``.
        embedding_vector: Serialised float32 bytes from the embedding service.
        model_version: Embedding model identifier (e.g. ``"stub-v0.1"``).
        dimension: Number of floats in the vector.

    Returns:
        Tuple of (User, Embedding) ORM objects.

    Raises:
        EmbeddingAlreadyExistsError: Active embedding already enrolled.
    """
    user, _ = await _get_or_create_user(db, external_id)

    existing = await _get_active_embedding(db, user.id, biometric_type)
    if existing is not None:
        raise EmbeddingAlreadyExistsError(external_id, biometric_type)

    embedding = Embedding(
        user_id=user.id,
        biometric_type=biometric_type,
        embedding_vector=embedding_vector,
        model_version=model_version,
        embedding_dimension=dimension,
        is_active=True,
    )
    db.add(embedding)
    await db.flush()  # populate embedding.id and created_at

    return user, embedding


async def update_enrollment(
    db: AsyncSession,
    external_id: str,
    biometric_type: str,
    embedding_vector: bytes,
    model_version: str,
) -> Embedding:
    """Replace an existing enrollment with a new embedding.

    The old Embedding row is soft-deleted (``is_active=False``) and a new
    active row is created to preserve history.

    Raises:
        UserNotFoundError: User doesn't exist or is inactive.
        EmbeddingNotFoundError: No active enrollment to update.
    """
    result = await db.execute(
        select(User).where(
            User.external_id == external_id,
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(external_id)

    existing = await _get_active_embedding(db, user.id, biometric_type)
    if existing is None:
        raise EmbeddingNotFoundError(external_id, biometric_type)

    # Soft-delete old embedding to preserve history
    existing.is_active = False
    await db.flush()

    dimension = len(embedding_vector) // 4  # float32 = 4 bytes
    new_embedding = Embedding(
        user_id=user.id,
        biometric_type=biometric_type,
        embedding_vector=embedding_vector,
        model_version=model_version,
        embedding_dimension=dimension,
        is_active=True,
    )
    db.add(new_embedding)
    await db.flush()

    return new_embedding


async def delete_enrollment(
    db: AsyncSession,
    external_id: str,
    biometric_type: str,
) -> None:
    """Soft-delete an enrollment by marking the embedding inactive.

    Raises:
        UserNotFoundError: User doesn't exist or is inactive.
        EmbeddingNotFoundError: No active enrollment found.
    """
    result = await db.execute(
        select(User).where(
            User.external_id == external_id,
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(external_id)

    existing = await _get_active_embedding(db, user.id, biometric_type)
    if existing is None:
        raise EmbeddingNotFoundError(external_id, biometric_type)

    existing.is_active = False
    await db.flush()


async def list_enrollments(
    db: AsyncSession,
    external_id: str,
) -> list[Embedding]:
    """Return all active enrollments for a user.

    Raises:
        UserNotFoundError: User doesn't exist or is inactive.
    """
    result = await db.execute(
        select(User).where(
            User.external_id == external_id,
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(external_id)

    emb_result = await db.execute(
        select(Embedding).where(
            Embedding.user_id == user.id,
            Embedding.is_active.is_(True),
        )
    )
    return list(emb_result.scalars().all())
