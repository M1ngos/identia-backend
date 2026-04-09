"""Tests for the enrollment API (/api/v1/enroll)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import make_fake_jpeg, to_b64

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENROLL_URL = "/api/v1/enroll"


def enroll_payload(
    user_id: str = "test-enroll-user",
    biometric_type: str = "face",
    seed: int = 0,
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "biometric_type": biometric_type,
        "biometric_data": to_b64(make_fake_jpeg(seed=seed)),
    }


# ---------------------------------------------------------------------------
# POST /enroll
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_enroll_creates_user_and_embedding(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Happy-path: new user + biometric should return 201 with expected fields."""
    response = await client.post(
        ENROLL_URL,
        json=enroll_payload(user_id="new-user-001"),
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == "new-user-001"
    assert data["biometric_type"] == "face"
    assert data["embedding_dimension"] == 512
    assert data["model_version"] == "stub-v0.1"
    assert "enrollment_id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_post_enroll_duplicate_returns_409(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Second enrollment for the same (user, biometric_type) must return 409."""
    payload = enroll_payload(user_id="dup-user-001")

    first = await client.post(ENROLL_URL, json=payload, headers=auth_headers)
    assert first.status_code == 201

    second = await client.post(ENROLL_URL, json=payload, headers=auth_headers)
    assert second.status_code == 409
    assert second.json()["code"] == "EMBEDDING_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_post_enroll_without_auth_returns_403(
    client: AsyncClient,
) -> None:
    """Requests without a JWT bearer token must be rejected (401 or 403)."""
    response = await client.post(ENROLL_URL, json=enroll_payload())
    # FastAPI >= 0.115 / Starlette >= 1.0 changed HTTPBearer to return 401
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_post_enroll_invalid_base64_returns_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Invalid base64 payload must fail at schema validation (422)."""
    payload = {
        "user_id": "b64-fail-user",
        "biometric_type": "face",
        "biometric_data": "!!!not-valid-base64!!!",
    }
    response = await client.post(ENROLL_URL, json=payload, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_enroll_data_too_small_returns_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Biometric data < 100 bytes must be rejected with 422."""
    import base64

    tiny = base64.b64encode(b"tiny").decode()
    payload = {
        "user_id": "small-user",
        "biometric_type": "face",
        "biometric_data": tiny,
    }
    response = await client.post(ENROLL_URL, json=payload, headers=auth_headers)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT /enroll/{user_id}/{biometric_type}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_enroll_replaces_embedding(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """PUT should accept new biometric data and return a fresh enrollment_id."""
    user_id = "update-user-001"

    # Enroll first
    create_resp = await client.post(
        ENROLL_URL,
        json=enroll_payload(user_id=user_id, seed=1),
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    original_enrollment_id = create_resp.json()["enrollment_id"]

    # Update with a different image
    update_resp = await client.put(
        f"{ENROLL_URL}/{user_id}/face",
        json={"biometric_data": to_b64(make_fake_jpeg(seed=99))},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["user_id"] == user_id
    # A new embedding row must have been created
    assert updated["enrollment_id"] != original_enrollment_id


@pytest.mark.asyncio
async def test_put_enroll_nonexistent_user_returns_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """PUT for an unknown user must return 404."""
    response = await client.put(
        f"{ENROLL_URL}/ghost-user-999/face",
        json={"biometric_data": to_b64(make_fake_jpeg())},
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /enroll/{user_id}/{biometric_type}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_enroll_removes_embedding(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """DELETE should soft-delete the embedding; subsequent GET returns empty list."""
    user_id = "delete-user-001"

    await client.post(
        ENROLL_URL,
        json=enroll_payload(user_id=user_id),
        headers=auth_headers,
    )

    del_resp = await client.delete(
        f"{ENROLL_URL}/{user_id}/face",
        headers=auth_headers,
    )
    assert del_resp.status_code == 200
    del_data = del_resp.json()
    assert del_data["user_id"] == user_id
    assert del_data["biometric_type"] == "face"

    # After deletion the list endpoint must return an empty list
    list_resp = await client.get(f"{ENROLL_URL}/{user_id}", headers=auth_headers)
    assert list_resp.status_code == 200
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_delete_enroll_nonexistent_returns_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """DELETE for a user with no enrollment returns 404."""
    response = await client.delete(
        f"{ENROLL_URL}/no-enrollment-user/face",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /enroll/{user_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_enrollments_lists_active(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET should return all active enrollments for the user."""
    user_id = "list-user-001"

    enroll_resp = await client.post(
        ENROLL_URL,
        json=enroll_payload(user_id=user_id, biometric_type="face"),
        headers=auth_headers,
    )
    assert enroll_resp.status_code == 201, enroll_resp.text

    response = await client.get(f"{ENROLL_URL}/{user_id}", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["user_id"] == user_id
    assert items[0]["biometric_type"] == "face"


@pytest.mark.asyncio
async def test_get_enrollments_unknown_user_returns_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get(
        f"{ENROLL_URL}/unknown-list-user-999",
        headers=auth_headers,
    )
    assert response.status_code == 404
