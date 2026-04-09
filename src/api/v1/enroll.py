"""Enrollment API — enroll, update, delete, and list biometric embeddings.

All routes require a valid JWT bearer token (``CurrentUserID``).

Rate limit: 10 enrollments per minute per IP address.
"""

from __future__ import annotations

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from src.core.config import settings
from src.core.dependencies import CurrentUserID, DBSession
from src.core.rate_limit import RateLimiter
from src.schemas.common import BiometricType
from src.schemas.enroll import (
    EnrollDeleteResponse,
    EnrollListItem,
    EnrollRequest,
    EnrollResponse,
    EnrollUpdateRequest,
)
from src.services import enrollment_service
from src.services.audit_service import log_audit
from src.services.embedding_service import (
    EmbeddingService,
    get_embedding_service,
    serialize_embedding,
)

router = APIRouter(prefix="/enroll", tags=["Enrollment"])

# Rate limiter: 10 enrollments / 60 s per IP
enroll_limiter = RateLimiter(calls=settings.ENROLL_RATE_LIMIT_PER_MINUTE)

# Typed dependency alias so route signatures stay concise
EmbeddingSvc = Annotated[EmbeddingService, Depends(get_embedding_service)]


@router.post(
    "",
    response_model=EnrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll a new biometric",
    description=(
        "Decode the base64 biometric data, extract an embedding, create the user "
        "record if absent, and persist the embedding.  Returns 409 if an active "
        "enrollment already exists for the same (user_id, biometric_type) pair."
    ),
)
async def enroll_biometric(
    request: Request,
    body: EnrollRequest,
    db: DBSession,
    current_user: CurrentUserID,
    svc: EmbeddingSvc,
    _rate: None = Depends(enroll_limiter),
) -> EnrollResponse:
    ip = request.client.host if request.client else None

    image_bytes = base64.b64decode(body.biometric_data)
    vector = svc.extract(image_bytes, body.biometric_type.value)
    vector_bytes = serialize_embedding(vector)

    user_db, embedding = await enrollment_service.enroll_user(
        db=db,
        external_id=body.user_id,
        biometric_type=body.biometric_type.value,
        embedding_vector=vector_bytes,
        model_version=svc.MODEL_VERSION,
        dimension=len(vector),
    )

    await log_audit(
        db=db,
        action="enroll",
        user_id=user_db.id,
        success=True,
        extra_data={"biometric_type": body.biometric_type.value},
        ip_address=ip,
    )

    return EnrollResponse(
        enrollment_id=str(embedding.id),
        user_id=body.user_id,
        biometric_type=body.biometric_type,
        embedding_dimension=embedding.embedding_dimension,
        model_version=embedding.model_version,
        created_at=embedding.created_at.isoformat(),
    )


@router.put(
    "/{user_id}/{biometric_type}",
    response_model=EnrollResponse,
    summary="Replace an existing enrollment",
    description=(
        "Soft-delete the current active embedding and enroll a new one. "
        "Returns 404 if the user or enrollment doesn't exist."
    ),
)
async def update_enrollment(
    request: Request,
    user_id: str,
    biometric_type: BiometricType,
    body: EnrollUpdateRequest,
    db: DBSession,
    current_user: CurrentUserID,
    svc: EmbeddingSvc,
    _rate: None = Depends(enroll_limiter),
) -> EnrollResponse:
    ip = request.client.host if request.client else None

    image_bytes = base64.b64decode(body.biometric_data)
    vector = svc.extract(image_bytes, biometric_type.value)
    vector_bytes = serialize_embedding(vector)

    embedding = await enrollment_service.update_enrollment(
        db=db,
        external_id=user_id,
        biometric_type=biometric_type.value,
        embedding_vector=vector_bytes,
        model_version=svc.MODEL_VERSION,
    )

    await log_audit(
        db=db,
        action="enroll_update",
        user_id=embedding.user_id,
        success=True,
        extra_data={"biometric_type": biometric_type.value},
        ip_address=ip,
    )

    return EnrollResponse(
        enrollment_id=str(embedding.id),
        user_id=user_id,
        biometric_type=biometric_type,
        embedding_dimension=embedding.embedding_dimension,
        model_version=embedding.model_version,
        created_at=embedding.created_at.isoformat(),
    )


@router.delete(
    "/{user_id}/{biometric_type}",
    response_model=EnrollDeleteResponse,
    summary="Revoke an enrollment",
    description="Soft-delete the active embedding. Returns 404 if not found.",
)
async def delete_enrollment(
    request: Request,
    user_id: str,
    biometric_type: BiometricType,
    db: DBSession,
    current_user: CurrentUserID,
    _rate: None = Depends(enroll_limiter),
) -> EnrollDeleteResponse:
    ip = request.client.host if request.client else None

    await enrollment_service.delete_enrollment(
        db=db,
        external_id=user_id,
        biometric_type=biometric_type.value,
    )

    await log_audit(
        db=db,
        action="enroll_delete",
        user_id=None,  # user UUID not returned by delete_enrollment
        success=True,
        extra_data={"biometric_type": biometric_type.value},
        ip_address=ip,
    )

    return EnrollDeleteResponse(
        user_id=user_id,
        biometric_type=biometric_type.value,
    )


@router.get(
    "/{user_id}",
    response_model=list[EnrollListItem],
    summary="List enrollments for a user",
    description="Return all active biometric enrollments for the given user.",
)
async def list_enrollments(
    user_id: str,
    db: DBSession,
    current_user: CurrentUserID,
) -> list[EnrollListItem]:
    embeddings = await enrollment_service.list_enrollments(db=db, external_id=user_id)

    return [
        EnrollListItem(
            enrollment_id=str(e.id),
            user_id=user_id,
            biometric_type=BiometricType(e.biometric_type),
            embedding_dimension=e.embedding_dimension,
            model_version=e.model_version,
            created_at=e.created_at.isoformat(),
        )
        for e in embeddings
    ]
