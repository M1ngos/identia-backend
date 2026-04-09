import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_ready(client: AsyncClient) -> None:
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
