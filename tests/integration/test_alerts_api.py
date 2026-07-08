"""Integration tests for /alerts endpoints."""

import pytest


@pytest.mark.integration
class TestAlertsAPI:
    async def test_list_alerts(self, async_client, auth_headers):
        resp = await async_client.get("/alerts/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_alerts_with_status_filter(self, async_client, auth_headers):
        resp = await async_client.get("/alerts/?status=open", headers=auth_headers)
        assert resp.status_code == 200

    async def test_get_alert_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/alerts/99999", headers=auth_headers)
        assert resp.status_code == 404
