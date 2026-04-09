import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, status

from src.core.config import settings
from src.core.dependencies import CurrentUserID, DBSession
from src.core.rate_limit import RateLimiter
from src.schemas.auth import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    TokenRequest,
    TokenResponse,
)
from src.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

token_limiter = RateLimiter(calls=20)


@router.post("/token", response_model=TokenResponse, summary="Exchange API key for JWT")
async def get_token(
    body: TokenRequest,
    db: DBSession,
    _rate: None = Depends(token_limiter),
) -> TokenResponse:
    token = await auth_service.issue_token_for_api_key(db, body.api_key)
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key",
)
async def create_api_key(
    body: ApiKeyCreateRequest,
    db: DBSession,
    current_user: CurrentUserID,
) -> ApiKeyCreateResponse:
    expires_at: datetime | None = None
    if body.expires_in_days is not None:
        expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days)

    api_key, plaintext = await auth_service.create_api_key(
        db,
        owner_id=current_user,
        label=body.label,
        expires_at=expires_at,
    )
    return ApiKeyCreateResponse(
        key_id=str(api_key.id),
        key=plaintext,
        prefix=api_key.key_prefix,
        label=api_key.label,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse], summary="List your API keys")
async def list_api_keys(
    db: DBSession,
    current_user: CurrentUserID,
) -> list[ApiKeyResponse]:
    keys = await auth_service.list_api_keys(db, owner_id=current_user)
    return [
        ApiKeyResponse(
            key_id=str(k.id),
            prefix=k.key_prefix,
            label=k.label,
            is_active=k.is_active,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
)
async def revoke_api_key(
    key_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUserID,
) -> None:
    await auth_service.revoke_api_key(db, key_id=key_id, owner_id=current_user)
