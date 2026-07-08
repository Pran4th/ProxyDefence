"""Integration tests for /analytics endpoints."""

import pytest


@pytest.mark.integration
class TestAnalyticsAPI:
    async def test_dashboard_stats(self, async_client, auth_headers):
        resp = await async_client.get("/analytics/dashboard", headers=auth_headers)
        assert resp.status_code == 200

    async def test_analytics_summary(self, async_client, auth_headers):
        resp = await async_client.get("/analytics/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_articles" in data
        assert "sentiment_distribution" in data

    async def test_threat_trends(self, async_client, auth_headers):
        resp = await async_client.get("/analytics/threat-trends", headers=auth_headers)
        assert resp.status_code == 200

    async def test_attack_graph(self, async_client, auth_headers):
        resp = await async_client.get("/analytics/graph", headers=auth_headers)
        assert resp.status_code == 200

    async def test_timeseries(self, async_client, auth_headers):
        resp = await async_client.get("/analytics/timeseries", headers=auth_headers)
        assert resp.status_code == 200

    async def test_top_entities(self, async_client, auth_headers):
        resp = await async_client.get("/analytics/entities", headers=auth_headers)
        assert resp.status_code == 200

    async def test_topic_breakdown(self, async_client, auth_headers):
        resp = await async_client.get("/analytics/topics", headers=auth_headers)
        assert resp.status_code == 200

    async def test_dashboard_v2(self, async_client, auth_headers):
        resp = await async_client.get("/analytics/dashboard-v2", headers=auth_headers)
        assert resp.status_code == 200
