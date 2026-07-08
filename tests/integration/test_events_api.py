"""Integration tests for /events endpoints."""

import pytest


@pytest.mark.integration
class TestEventsAPI:
    async def test_list_events(self, async_client, auth_headers):
        resp = await async_client.get("/events/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_event_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/events/99999", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_event_articles_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/events/99999/articles", headers=auth_headers)
        assert resp.status_code == 200
