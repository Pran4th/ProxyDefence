"""Integration tests for /graph endpoints."""

import pytest


@pytest.mark.integration
class TestGraphAPI:
    async def test_graph_network(self, async_client, auth_headers):
        resp = await async_client.get("/graph/network", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data

    async def test_entity_graph(self, async_client, auth_headers):
        resp = await async_client.get("/graph/Iran", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
