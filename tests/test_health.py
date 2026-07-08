import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(async_client: AsyncClient):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_liveness(async_client: AsyncClient):
    resp = await async_client.get("/liveness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness(async_client: AsyncClient):
    resp = await async_client.get("/readiness")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_version(async_client: AsyncClient):
    resp = await async_client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "service" in data
    assert "version" in data
