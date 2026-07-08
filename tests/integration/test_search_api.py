"""Integration tests for /search endpoints."""

import pytest


@pytest.mark.integration
class TestSearchAPI:
    async def test_search_requires_query(self, async_client, auth_headers):
        resp = await async_client.get("/search/", headers=auth_headers)
        assert resp.status_code == 422

    async def test_search_returns_results(self, async_client, auth_headers):
        resp = await async_client.get("/search/?q=Iran", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "total_results" in data
        assert "results" in data
