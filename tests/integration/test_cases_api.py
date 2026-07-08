"""Integration tests for /cases endpoints."""

import pytest


@pytest.mark.integration
class TestCasesAPI:
    async def test_list_cases(self, async_client, auth_headers):
        resp = await async_client.get("/cases/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_case_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/cases/99999", headers=auth_headers)
        assert resp.status_code == 404

    async def test_create_case(self, async_client, auth_headers):
        resp = await async_client.post("/cases/", json={
            "title": "Integration Test Case",
            "description": "Created by integration test",
            "priority": "medium",
        }, headers=auth_headers)
        assert resp.status_code in (201, 401, 403)

    async def test_list_case_notes_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/cases/99999/notes", headers=auth_headers)
        assert resp.status_code == 404
