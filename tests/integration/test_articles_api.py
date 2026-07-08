"""Integration tests for /articles endpoints."""

import pytest


@pytest.mark.integration
class TestArticlesAPI:
    async def test_list_articles(self, async_client, auth_headers):
        resp = await async_client.get("/articles/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_articles_with_limit(self, async_client, auth_headers):
        resp = await async_client.get("/articles/?limit=5", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) <= 5

    async def test_list_articles_with_sentiment_filter(self, async_client, auth_headers):
        resp = await async_client.get("/articles/?sentiment=negative", headers=auth_headers)
        assert resp.status_code == 200

    async def test_get_article_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/articles/99999", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_article_entities_not_found(self, async_client, auth_headers):
        resp = await async_client.get("/articles/99999/entities", headers=auth_headers)
        assert resp.status_code == 404

    async def test_unauthorized_access(self, async_client):
        resp = await async_client.get("/articles/")
        assert resp.status_code == 401
