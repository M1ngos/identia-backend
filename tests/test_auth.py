from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.api_key import ApiKey
from src.services.auth_service import create_access_token, create_api_key


@pytest.mark.asyncio
async def test_get_token_with_valid_key(
    client: AsyncClient, sample_api_key: tuple[ApiKey, str]
) -> None:
    _, plaintext = sample_api_key
    response = await client.post("/api/v1/auth/token", json={"api_key": plaintext})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800


@pytest.mark.asyncio
async def test_get_token_with_invalid_key(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/token", json={"api_key": "bsk_live_invalidkeyvalue"})
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_API_KEY"


@pytest.mark.asyncio
async def test_get_token_with_expired_key(client: AsyncClient, db: AsyncSession) -> None:
    expired_key_model, plaintext = await create_api_key(
        db,
        owner_id="expired-user",
        label="expired",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    await db.commit()
    response = await client.post("/api/v1/auth/token", json={"api_key": plaintext})
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_API_KEY"


@pytest.mark.asyncio
async def test_get_token_wrong_format(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/token", json={"api_key": "wrong_prefix_key"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/auth/api-keys",
        json={"label": "my sdk key", "expires_in_days": 90},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"].startswith("bsk_live_")
    assert data["label"] == "my sdk key"
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_list_api_keys(
    client: AsyncClient, auth_headers: dict[str, str], sample_api_key: tuple[ApiKey, str]
) -> None:
    response = await client.get("/api/v1/auth/api-keys", headers=auth_headers)
    assert response.status_code == 200
    keys = response.json()
    assert isinstance(keys, list)
    assert len(keys) >= 1
    # all returned keys belong to the authenticated user — no key field exposed
    for k in keys:
        assert "key" not in k
        assert "key_id" in k


@pytest.mark.asyncio
async def test_revoke_api_key(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
) -> None:
    new_key, plaintext = await create_api_key(
        db, owner_id="test-user-001", label="to revoke", expires_at=None
    )
    await db.commit()

    response = await client.delete(f"/api/v1/auth/api-keys/{new_key.id}", headers=auth_headers)
    assert response.status_code == 204

    # key can no longer be used
    token_resp = await client.post("/api/v1/auth/token", json={"api_key": plaintext})
    assert token_resp.status_code == 401


@pytest.mark.asyncio
async def test_revoke_other_users_key(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
) -> None:
    other_key, _ = await create_api_key(
        db, owner_id="other-user-999", label="other", expires_at=None
    )
    await db.commit()

    response = await client.delete(f"/api/v1/auth/api-keys/{other_key.id}", headers=auth_headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_jwt_required_on_protected_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/api-keys")
    # FastAPI >= 0.115 / Starlette >= 1.0 changed HTTPBearer to return 401 (was 403)
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_expired_jwt_rejected(client: AsyncClient) -> None:
    token = create_access_token("some-user", expires_delta=timedelta(seconds=-1))
    response = await client.get(
        "/api/v1/auth/api-keys",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
