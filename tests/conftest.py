"""Test configuration and fixtures.

Architecture notes:
- ``setup_test_db`` is a *synchronous* session-scoped fixture that creates/drops
  tables via ``asyncio.run()``.  This avoids the pytest-asyncio "Future attached
  to different loop" error that occurs when session-scoped async fixtures share
  an event loop with function-scoped test coroutines.
- All other async fixtures are function-scoped and use ``NullPool`` so every
  test gets fresh asyncpg connections that are bound to its own event loop.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.database import Base, get_db
from src.main import app
from src.models.api_key import ApiKey
from src.services.auth_service import create_api_key

TEST_DATABASE_URL = "postgresql+asyncpg://dev:dev@localhost:5432/biometric_test"


# ---------------------------------------------------------------------------
# Test image helpers
# ---------------------------------------------------------------------------


def make_fake_jpeg(seed: int = 0) -> bytes:
    """Return a minimal fake JPEG (starts with SOI marker, > 100 bytes)."""
    magic = b"\xff\xd8\xff\xe0"
    content = bytes([(seed + i) % 256 for i in range(200)])
    return magic + content


def to_b64(data: bytes) -> str:
    """Base64-encode bytes to a UTF-8 string."""
    return base64.b64encode(data).decode()


# ---------------------------------------------------------------------------
# Database schema setup — sync fixture, uses asyncio.run() internally
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def setup_test_db() -> None:
    """Create all tables once per test session, drop them afterward.

    Using a sync fixture + asyncio.run() keeps this isolated from
    pytest-asyncio's per-function event loops.
    """

    async def _create() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _drop() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_drop())


# ---------------------------------------------------------------------------
# Rate-limiter reset — clear in-memory state before every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_rate_limiters() -> None:
    """Clear rate-limiter buckets so tests don't bleed into each other."""
    from src.api.v1.auth import token_limiter
    from src.api.v1.enroll import enroll_limiter
    from src.api.v1.verify import verify_limiter

    token_limiter._store.clear()
    enroll_limiter._store.clear()
    verify_limiter._store.clear()


# ---------------------------------------------------------------------------
# Per-test database session — NullPool keeps each connection on the test loop
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Per-test async session — rolls back all changes at teardown."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with DB dependency overridden to use the test session."""
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sample_api_key(db: AsyncSession) -> tuple[ApiKey, str]:
    key_model, plaintext = await create_api_key(
        db,
        owner_id="test-user-001",
        label="test key",
        expires_at=None,
    )
    await db.commit()
    await db.refresh(key_model)
    return key_model, plaintext


@pytest_asyncio.fixture
async def auth_headers(
    client: AsyncClient,
    sample_api_key: tuple[ApiKey, str],
) -> dict[str, str]:
    _, plaintext = sample_api_key
    response = await client.post("/api/v1/auth/token", json={"api_key": plaintext})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Enrollment fixtures (for verification tests)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def enrolled_face_user(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> dict[str, object]:
    """Enroll 'enrolled-face-001' with a face biometric via the HTTP API.

    Returns a dict with ``user_id``, ``image`` (raw bytes), and
    ``image_b64`` (base64 string) so tests can re-use the same image.
    """
    image = make_fake_jpeg(seed=42)
    response = await client.post(
        "/api/v1/enroll",
        json={
            "user_id": "enrolled-face-001",
            "biometric_type": "face",
            "biometric_data": to_b64(image),
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return {
        "user_id": "enrolled-face-001",
        "image": image,
        "image_b64": to_b64(image),
        "enrollment": response.json(),
    }
