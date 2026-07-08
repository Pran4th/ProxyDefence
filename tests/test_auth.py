import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(async_client: AsyncClient):
    payload = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPass123!",
    }
    resp = await async_client.post("/auth/register", json=payload)
    assert resp.status_code in (201, 409)


@pytest.mark.asyncio
async def test_login(async_client: AsyncClient):
    payload = {
        "email": "test@example.com",
        "password": "TestPass123!",
    }
    resp = await async_client.post("/auth/login", json=payload)
    if resp.status_code == 200:
        data = resp.json()
        assert "access_token" in data
    else:
        assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_me_unauthorized(async_client: AsyncClient):
    resp = await async_client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate(async_client: AsyncClient):
    payload = {
        "email": "dupe@example.com",
        "username": "dupeuser",
        "password": "TestPass123!",
    }
    resp1 = await async_client.post("/auth/register", json=payload)
    assert resp1.status_code in (201, 409)

    resp2 = await async_client.post("/auth/register", json=payload)
    assert resp2.status_code == 409
