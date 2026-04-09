from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.exceptions import AuthenticationError, InvalidAPIKeyError

security = HTTPBearer()


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> str:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token: missing user ID")
        return user_id
    except JWTError as e:
        raise AuthenticationError(f"Invalid or expired token: {e}") from e


async def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> str:
    if not x_api_key:
        raise InvalidAPIKeyError("API key is required")
    from src.services.auth_service import validate_api_key

    return await validate_api_key(db, x_api_key)


DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUserID = Annotated[str, Depends(get_current_user_id)]
APIKey = Annotated[str, Depends(verify_api_key)]
