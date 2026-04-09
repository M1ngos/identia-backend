import secrets
import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt  # type: ignore[import-untyped]
from passlib.context import CryptContext  # type: ignore[import-untyped]
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import InvalidAPIKeyError
from src.models.api_key import ApiKey

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key() -> tuple[str, str]:
    """Returns (full_key, prefix)."""
    full_key = settings.API_KEY_PREFIX + secrets.token_urlsafe(32)
    prefix = full_key[:16]
    return full_key, prefix


def hash_key(full_key: str) -> str:
    return str(_pwd_context.hash(full_key))


def verify_key(full_key: str, hashed: str) -> bool:
    result: bool = _pwd_context.verify(full_key, hashed)
    return result


async def create_api_key(
    db: AsyncSession,
    owner_id: str,
    label: str | None,
    expires_at: datetime | None,
) -> tuple[ApiKey, str]:
    """Creates an ApiKey row. Returns (model, plaintext_key)."""
    full_key, prefix = generate_api_key()
    api_key = ApiKey(
        key_prefix=prefix,
        key_hash=hash_key(full_key),
        owner_id=owner_id,
        label=label,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.flush()
    return api_key, full_key


async def revoke_api_key(
    db: AsyncSession,
    key_id: uuid.UUID,
    owner_id: str,
) -> None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.owner_id == owner_id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise InvalidAPIKeyError("API key not found or access denied")
    api_key.is_active = False


async def list_api_keys(db: AsyncSession, owner_id: str) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.owner_id == owner_id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def validate_api_key(db: AsyncSession, full_key: str) -> str:
    """Validates a full API key. Returns owner_id on success, raises InvalidAPIKeyError on failure."""
    if len(full_key) < 16:
        raise InvalidAPIKeyError()

    prefix = full_key[:16]
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise InvalidAPIKeyError()

    if not verify_key(full_key, api_key.key_hash):
        raise InvalidAPIKeyError()

    if api_key.expires_at is not None and datetime.now(UTC) > api_key.expires_at:
        raise InvalidAPIKeyError("API key has expired")

    await db.execute(
        update(ApiKey).where(ApiKey.id == api_key.id).values(last_used_at=datetime.now(UTC))
    )

    return api_key.owner_id


def create_access_token(
    external_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": external_id,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return str(jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM))


async def issue_token_for_api_key(db: AsyncSession, full_key: str) -> str:
    owner_id = await validate_api_key(db, full_key)
    return create_access_token(owner_id)
