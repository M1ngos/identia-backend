"""Shared audit-logging helper.

Every enrollment and verification operation writes an AuditLog row.
This module exposes a single coroutine that adds the row to the session;
the caller is responsible for committing (FastAPI's get_db does this
automatically at the end of each request).

PII policy: ``extra_data`` must never contain raw biometric data or
personally-identifiable information — only type labels and error codes.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit import AuditLog


async def log_audit(
    db: AsyncSession,
    action: str,
    user_id: uuid.UUID | None,
    success: bool,
    confidence_score: float | None = None,
    extra_data: dict[str, object] | None = None,
    ip_address: str | None = None,
) -> None:
    """Append an AuditLog entry to the current database session.

    Args:
        db: Active SQLAlchemy async session.
        action: One of ``"enroll"``, ``"enroll_update"``, ``"enroll_delete"``,
            ``"verify"``.
        user_id: Internal UUID of the affected user, or ``None`` if unknown.
        success: Whether the operation completed successfully.
        confidence_score: Similarity score (verify operations only).
        extra_data: Arbitrary JSON-serialisable metadata. **No PII.**
        ip_address: Client IP for security audit trail.
    """
    audit = AuditLog(
        action=action,
        user_id=user_id,
        success=success,
        confidence_score=confidence_score,
        extra_data=extra_data,
        ip_address=ip_address,
    )
    db.add(audit)
