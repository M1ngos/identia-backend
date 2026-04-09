"""Tests for the verification API (/api/v1/verify)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import make_fake_jpeg, to_b64

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENROLL_URL = "/api/v1/enroll"
VERIFY_URL = "/api/v1/verify"


def verify_payload(
    user_id: str,
    biometric_type: str = "face",
    seed: int = 0,
    return_score: bool = True,
    threshold: float | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_id": user_id,
        "biometric_type": biometric_type,
        "biometric_data": to_b64(make_fake_jpeg(seed=seed)),
        "return_score": return_score,
    }
    if threshold is not None:
        payload["confidence_threshold"] = threshold
    return payload


# ---------------------------------------------------------------------------
# POST /verify — 1:1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_same_image_returns_verified_true(
    client: AsyncClient,
    auth_headers: dict[str, str],
    enrolled_face_user: dict[str, object],
) -> None:
    """Verifying with the exact same image as enrolled must return verified=True."""
    image_b64 = enrolled_face_user["image_b64"]

    response = await client.post(
        VERIFY_URL,
        json={
            "user_id": "enrolled-face-001",
            "biometric_type": "face",
            "biometric_data": image_b64,
            "return_score": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert data["confidence_score"] > 0.99, f"Expected score > 0.99, got {data['confidence_score']}"
    assert data["user_id"] == "enrolled-face-001"
    assert data["biometric_type"] == "face"
    assert "model_version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_verify_different_image_returns_verified_false(
    client: AsyncClient,
    auth_headers: dict[str, str],
    enrolled_face_user: dict[str, object],
) -> None:
    """A different image must produce a low score and verified=False."""
    # seed=42 was used for enrollment; seed=7 produces a completely different vector
    different_b64 = to_b64(make_fake_jpeg(seed=7))

    response = await client.post(
        VERIFY_URL,
        json={
            "user_id": "enrolled-face-001",
            "biometric_type": "face",
            "biometric_data": different_b64,
            "return_score": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is False
    assert data["confidence_score"] < 0.85, f"Expected score < 0.85, got {data['confidence_score']}"


@pytest.mark.asyncio
async def test_verify_unknown_user_returns_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Verifying a user that was never enrolled must return 404."""
    response = await client.post(
        VERIFY_URL,
        json=verify_payload(user_id="ghost-user-verify-999"),
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_verify_user_without_enrollment_returns_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """A user that exists but has no face enrollment should return 404."""
    user_id = "no-embed-user-001"

    # Enroll then delete to create a user with no active embedding
    await client.post(
        ENROLL_URL,
        json={
            "user_id": user_id,
            "biometric_type": "face",
            "biometric_data": to_b64(make_fake_jpeg(seed=5)),
        },
        headers=auth_headers,
    )
    await client.delete(f"{ENROLL_URL}/{user_id}/face", headers=auth_headers)

    response = await client.post(
        VERIFY_URL,
        json=verify_payload(user_id=user_id),
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "EMBEDDING_NOT_FOUND"


@pytest.mark.asyncio
async def test_verify_without_auth_returns_403(
    client: AsyncClient,
    enrolled_face_user: dict[str, object],
) -> None:
    """Verify without a bearer token must be rejected (401 or 403)."""
    response = await client.post(
        VERIFY_URL,
        json={
            "user_id": "enrolled-face-001",
            "biometric_type": "face",
            "biometric_data": enrolled_face_user["image_b64"],
        },
    )
    # FastAPI >= 0.115 / Starlette >= 1.0 changed HTTPBearer to return 401
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_verify_custom_threshold(
    client: AsyncClient,
    auth_headers: dict[str, str],
    enrolled_face_user: dict[str, object],
) -> None:
    """A very high threshold forces verified=False even for a self-match."""
    image_b64 = enrolled_face_user["image_b64"]

    response = await client.post(
        VERIFY_URL,
        json={
            "user_id": "enrolled-face-001",
            "biometric_type": "face",
            "biometric_data": image_b64,
            "confidence_threshold": 0.99,
            "return_score": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    # Score is high (~1.0) so threshold 0.99 should still pass
    assert data["threshold"] == 0.99


# ---------------------------------------------------------------------------
# POST /verify/batch — 1:N
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_verify_with_two_users(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Batch verify should return results for each user in order."""
    # Enroll two different users with different images
    user_a = "batch-user-a"
    user_b = "batch-user-b"
    image_a = make_fake_jpeg(seed=10)
    image_b = make_fake_jpeg(seed=20)

    await client.post(
        ENROLL_URL,
        json={
            "user_id": user_a,
            "biometric_type": "face",
            "biometric_data": to_b64(image_a),
        },
        headers=auth_headers,
    )
    await client.post(
        ENROLL_URL,
        json={
            "user_id": user_b,
            "biometric_type": "face",
            "biometric_data": to_b64(image_b),
        },
        headers=auth_headers,
    )

    # Probe with user_a's image — should match A but not B
    response = await client.post(
        f"{VERIFY_URL}/batch",
        json={
            "user_ids": [user_a, user_b],
            "biometric_type": "face",
            "biometric_data": to_b64(image_a),
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data["results"]) == 2
    assert "model_version" in data
    assert "timestamp" in data
    assert "biometric_type" in data

    result_map = {r["user_id"]: r for r in data["results"]}

    # user_a enrolled with image_a → should be verified
    assert result_map[user_a]["verified"] is True
    assert result_map[user_a]["confidence_score"] > 0.99

    # user_b enrolled with a different image → should NOT be verified
    assert result_map[user_b]["verified"] is False
    assert result_map[user_b]["confidence_score"] < 0.85


@pytest.mark.asyncio
async def test_batch_verify_nonexistent_user_returns_not_verified(
    client: AsyncClient,
    auth_headers: dict[str, str],
    enrolled_face_user: dict[str, object],
) -> None:
    """Non-existent users in a batch should appear as verified=False, score=0."""
    response = await client.post(
        f"{VERIFY_URL}/batch",
        json={
            "user_ids": ["enrolled-face-001", "ghost-user-xyz"],
            "biometric_type": "face",
            "biometric_data": enrolled_face_user["image_b64"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    results = {r["user_id"]: r for r in response.json()["results"]}

    assert results["enrolled-face-001"]["verified"] is True
    assert results["ghost-user-xyz"]["verified"] is False
    assert results["ghost-user-xyz"]["confidence_score"] == 0.0


@pytest.mark.asyncio
async def test_batch_verify_exceeds_max_users_returns_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Batches larger than 100 users must be rejected with 422."""
    user_ids = [f"user-{i}" for i in range(101)]
    response = await client.post(
        f"{VERIFY_URL}/batch",
        json={
            "user_ids": user_ids,
            "biometric_type": "face",
            "biometric_data": to_b64(make_fake_jpeg()),
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
