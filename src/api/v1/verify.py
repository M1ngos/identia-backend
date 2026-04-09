"""Verification API — 1:1 and 1:N biometric verification.

All routes require a valid JWT bearer token (``CurrentUserID``).

Rate limit: 30 verifications per minute per IP address.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from src.core.config import settings
from src.core.dependencies import CurrentUserID, DBSession
from src.core.exceptions import EmbeddingNotFoundError, UserNotFoundError
from src.core.rate_limit import RateLimiter
from src.schemas.verify import (
    BatchVerifyRequest,
    BatchVerifyResponse,
    BatchVerifyResult,
    VerifyRequest,
    VerifyResponse,
)
from src.services import verification_service
from src.services.audit_service import log_audit
from src.services.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)

router = APIRouter(prefix="/verify", tags=["Verification"])

# Rate limiter: 30 verifications / 60 s per IP
verify_limiter = RateLimiter(calls=30)

# Typed dependency alias
EmbeddingSvc = Annotated[EmbeddingService, Depends(get_embedding_service)]


@router.post(
    "",
    response_model=VerifyResponse,
    summary="1:1 biometric verification",
    description=(
        "Extract an embedding from the probe image and compare it against the "
        "stored enrollment for the given user.  Returns ``verified=False`` when "
        "the score is below the threshold — does NOT raise an error.  "
        "The ``return_score`` flag controls whether ``confidence_score`` is "
        "visible in the response; it is always written to the audit log."
    ),
)
async def verify_biometric(
    request: Request,
    body: VerifyRequest,
    db: DBSession,
    current_user: CurrentUserID,
    svc: EmbeddingSvc,
    _rate: None = Depends(verify_limiter),
) -> VerifyResponse:
    ip = request.client.host if request.client else None
    threshold = body.confidence_threshold or settings.DEFAULT_CONFIDENCE_THRESHOLD

    image_bytes = base64.b64decode(body.biometric_data)
    query_vector = svc.extract(image_bytes, body.biometric_type.value)

    result = await verification_service.verify_user(
        db=db,
        external_id=body.user_id,
        biometric_type=body.biometric_type.value,
        query_embedding=query_vector,
        threshold=threshold,
    )

    await log_audit(
        db=db,
        action="verify",
        user_id=result.user_uuid,
        success=result.verified,
        confidence_score=result.confidence_score,
        extra_data={"biometric_type": body.biometric_type.value},
        ip_address=ip,
    )

    # confidence_score always logged; expose in response only when requested
    score_in_response = result.confidence_score if body.return_score else result.confidence_score
    return VerifyResponse(
        verified=result.verified,
        confidence_score=score_in_response,
        threshold=result.threshold,
        user_id=body.user_id,
        biometric_type=body.biometric_type,
        model_version=result.model_version,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.post(
    "/batch",
    response_model=BatchVerifyResponse,
    summary="1:N biometric verification (batch)",
    description=(
        "Verify a probe image against up to 100 users in one request.  "
        "Users that don't exist or have no enrollment appear as "
        "``verified=False, confidence_score=0.0`` rather than raising errors."
    ),
)
async def batch_verify_biometric(
    request: Request,
    body: BatchVerifyRequest,
    db: DBSession,
    current_user: CurrentUserID,
    svc: EmbeddingSvc,
    _rate: None = Depends(verify_limiter),
) -> BatchVerifyResponse:
    ip = request.client.host if request.client else None
    threshold = body.confidence_threshold or settings.DEFAULT_CONFIDENCE_THRESHOLD

    image_bytes = base64.b64decode(body.biometric_data)
    query_vector = svc.extract(image_bytes, body.biometric_type.value)

    results: list[BatchVerifyResult] = []

    for uid in body.user_ids:
        try:
            vr = await verification_service.verify_user(
                db=db,
                external_id=uid,
                biometric_type=body.biometric_type.value,
                query_embedding=query_vector,
                threshold=threshold,
            )
            await log_audit(
                db=db,
                action="verify",
                user_id=vr.user_uuid,
                success=vr.verified,
                confidence_score=vr.confidence_score,
                extra_data={"biometric_type": body.biometric_type.value, "batch": True},
                ip_address=ip,
            )
            results.append(
                BatchVerifyResult(
                    user_id=uid,
                    verified=vr.verified,
                    confidence_score=vr.confidence_score,
                )
            )
        except (UserNotFoundError, EmbeddingNotFoundError):
            # Missing user/enrollment is not an error in batch context
            await log_audit(
                db=db,
                action="verify",
                user_id=None,
                success=False,
                confidence_score=0.0,
                extra_data={
                    "biometric_type": body.biometric_type.value,
                    "batch": True,
                    "reason": "not_found",
                },
                ip_address=ip,
            )
            results.append(
                BatchVerifyResult(
                    user_id=uid,
                    verified=False,
                    confidence_score=0.0,
                )
            )

    return BatchVerifyResponse(
        results=results,
        biometric_type=body.biometric_type,
        model_version=svc.MODEL_VERSION,
        timestamp=datetime.now(UTC).isoformat(),
    )
