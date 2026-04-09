"""Database-layer service for biometric verification.

Loads stored embeddings and delegates similarity scoring to EmbeddingService.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import EmbeddingNotFoundError, UserNotFoundError
from src.models.embedding import Embedding
from src.models.user import User
from src.services.embedding_service import deserialize_embedding, embedding_service


@dataclass
class VerifyResult:
    """Outcome of a single verification check."""

    verified: bool
    confidence_score: float
    threshold: float
    model_version: str
    user_uuid: uuid.UUID | None = field(default=None)


async def verify_user(
    db: AsyncSession,
    external_id: str,
    biometric_type: str,
    query_embedding: list[float],
    threshold: float,
) -> VerifyResult:
    """Verify a user's identity against their stored embedding.

    Steps:
    1. Look up User by external_id.
    2. Load the active Embedding for the requested biometric_type.
    3. Deserialise the stored vector and compute cosine similarity.
    4. Return a VerifyResult — never raises on low score (caller decides).

    Args:
        db: Active async session.
        external_id: Caller-supplied user identifier.
        biometric_type: e.g. ``"face"``.
        query_embedding: Already-extracted embedding of the probe image.
        threshold: Minimum similarity score to consider verified.

    Returns:
        VerifyResult with verified flag, score, threshold, and model version.

    Raises:
        UserNotFoundError: User doesn't exist or is inactive.
        EmbeddingNotFoundError: No active enrollment for this biometric type.
    """
    user_result = await db.execute(
        select(User).where(
            User.external_id == external_id,
            User.is_active.is_(True),
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(external_id)

    emb_result = await db.execute(
        select(Embedding).where(
            Embedding.user_id == user.id,
            Embedding.biometric_type == biometric_type,
            Embedding.is_active.is_(True),
        )
    )
    stored_embedding = emb_result.scalar_one_or_none()
    if stored_embedding is None:
        raise EmbeddingNotFoundError(external_id, biometric_type)

    stored_vector = deserialize_embedding(stored_embedding.embedding_vector)
    score = embedding_service.compute_similarity(query_embedding, stored_vector)

    return VerifyResult(
        verified=score >= threshold,
        confidence_score=score,
        threshold=threshold,
        model_version=stored_embedding.model_version,
        user_uuid=user.id,
    )
