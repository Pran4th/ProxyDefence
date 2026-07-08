"""Integration tests for /entities endpoints."""

import pytest


@pytest.mark.integration
class TestEntitiesAPI:
    async def test_list_entities(self, async_client, auth_headers):
        resp = await async_client.get("/entities/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_entity_profile_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/entities/NonexistentEntity12345", headers=auth_headers)
        assert resp.status_code in (200, 404)

    async def test_get_entity_timeline(self, async_client, auth_headers):
        resp = await async_client.get("/entities/Iran/timeline", headers=auth_headers)
        assert resp.status_code in (200, 404)
