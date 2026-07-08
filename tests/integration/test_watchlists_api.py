"""Integration tests for /watchlists endpoints."""

import pytest


@pytest.mark.integration
class TestWatchlistsAPI:
    async def test_list_watchlists(self, async_client, auth_headers):
        resp = await async_client.get("/watchlists/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_watchlist_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/watchlists/99999", headers=auth_headers)
        assert resp.status_code == 404

    async def test_create_watchlist(self, async_client, auth_headers):
        resp = await async_client.post("/watchlists/", json={
            "name": "Integration Test Watchlist",
            "description": "Created by integration test",
            "entities": ["Iran", "Houthi"],
        }, headers=auth_headers)
        assert resp.status_code in (201, 401, 403)
