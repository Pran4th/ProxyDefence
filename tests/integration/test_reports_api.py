"""Integration tests for /reports endpoints."""

import pytest


@pytest.mark.integration
class TestReportsAPI:
    async def test_list_reports(self, async_client, auth_headers):
        resp = await async_client.get("/reports/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_report_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/reports/99999", headers=auth_headers)
        assert resp.status_code == 404
