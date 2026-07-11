"""Integration tests for the unauthenticated /public/articles endpoints.

Uses live_client (real DB) rather than async_client (mocked pool) because the
whole point of these tests is to verify the actual column allowlist against
real rows -- the mocked pool always returns an empty list/None, which would
make the "sensitive fields are absent" assertions vacuously true.
"""

import pytest

SENSITIVE_FIELDS = {"content", "article_id", "url", "confidence"}
EXPECTED_FIELDS = {"id", "title", "source", "topic", "summary", "risk_level", "threat_score", "sentiment", "published_at"}


@pytest.mark.integration
class TestPublicArticlesAPI:
    async def test_list_no_auth_required(self, live_client):
        resp = await live_client.get("/public/articles?limit=5")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)

    async def test_list_narrow_field_set(self, live_client):
        resp = await live_client.get("/public/articles?limit=5")
        assert resp.status_code == 200
        items = resp.json()
        if not items:
            pytest.skip("no processed_articles rows available in this environment")
        for item in items:
            assert not (SENSITIVE_FIELDS & item.keys()), f"leaked sensitive field(s): {SENSITIVE_FIELDS & item.keys()}"
            assert item.keys() <= EXPECTED_FIELDS

    async def test_get_by_id_no_auth_required(self, live_client):
        listing = await live_client.get("/public/articles?limit=1")
        items = listing.json()
        if not items:
            pytest.skip("no processed_articles rows available in this environment")
        article_id = items[0]["id"]

        resp = await live_client.get(f"/public/articles/{article_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == article_id
        assert not (SENSITIVE_FIELDS & body.keys())

    async def test_get_by_id_not_found(self, live_client):
        resp = await live_client.get("/public/articles/99999999")
        assert resp.status_code == 404

    async def test_list_respects_limit(self, live_client):
        resp = await live_client.get("/public/articles?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2
