"""Integration tests for /auth endpoints."""

import pytest


@pytest.mark.integration
class TestAuthAPI:
    async def test_register_new_user(self, async_client):
        payload = {
            "email": f"inttest_{__import__('time').time()}@test.local",
            "username": f"intuser_{__import__('time').time()}",
            "password": "IntegrationPass1!",
        }
        resp = await async_client.post("/auth/register", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "user" in data

    async def test_register_duplicate(self, async_client):
        payload = {
            "email": "dup_int@test.local",
            "username": "dup_int_user",
            "password": "DupPass123!",
        }
        await async_client.post("/auth/register", json=payload)
        resp = await async_client.post("/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_login_success(self, async_client):
        payload = {
            "email": f"login_{__import__('time').time()}@test.local",
            "username": f"loginuser_{__import__('time').time()}",
            "password": "LoginPass123!",
        }
        await async_client.post("/auth/register", json=payload)

        login = {"email": payload["email"], "password": payload["password"]}
        resp = await async_client.post("/auth/login", json=login)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_login_invalid_credentials(self, async_client):
        resp = await async_client.post("/auth/login", json={
            "email": "nonexistent@test.local",
            "password": "WrongPass123!",
        })
        assert resp.status_code == 401

    async def test_me_authenticated(self, async_client):
        payload = {
            "email": f"me_{__import__('time').time()}@test.local",
            "username": f"meuser_{__import__('time').time()}",
            "password": "MePass123!",
        }
        reg = await async_client.post("/auth/register", json=payload)
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        resp = await async_client.get("/auth/me", headers=headers)
        assert resp.status_code == 200
        assert "email" in resp.json()

    async def test_me_unauthorized(self, async_client):
        resp = await async_client.get("/auth/me")
        assert resp.status_code == 401
