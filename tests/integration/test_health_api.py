"""Integration tests for health API endpoints.

These tests send real HTTP requests to the modular-api and verify
the full response shape.
"""

import pytest


@pytest.mark.integration
class TestHealthEndpoint:
    async def test_health_returns_200(self, async_client):
        resp = await async_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "service" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "started_at" in data
        assert "dependencies" in data

    async def test_liveness_returns_200(self, async_client):
        resp = await async_client.get("/liveness")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    async def test_readiness_returns_200(self, async_client):
        resp = await async_client.get("/readiness")
        assert resp.status_code in (200, 503)

    async def test_version_returns_service_and_version(self, async_client):
        resp = await async_client.get("/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "service" in data
        assert "version" in data

    async def test_status_returns_full_info(self, async_client):
        resp = await async_client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "service" in data
        assert "dependencies" in data
        assert "timestamp" in data

    async def test_root_returns_200(self, async_client):
        resp = await async_client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
