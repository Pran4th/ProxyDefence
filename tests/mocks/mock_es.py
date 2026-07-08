"""Mock Elasticsearch clients for unit tests."""

from unittest.mock import AsyncMock, MagicMock


class MockAsyncElasticsearch:
    """Mock for elasticsearch.AsyncElasticsearch."""

    def __init__(self):
        self.indexed: list[dict] = []
        self._ping_result = True

    async def ping(self, *args, **kwargs) -> bool:
        return self._ping_result

    async def index(self, index: str, body: dict, **kwargs) -> dict:
        self.indexed.append({"index": index, "body": body, **kwargs})
        return {"result": "created", "_id": "test-id"}

    async def search(self, index: str, body: dict, **kwargs) -> dict:
        return {
            "hits": {
                "total": {"value": 0},
                "hits": [],
            }
        }

    async def delete(self, index: str, id: str, **kwargs) -> dict:
        return {"result": "deleted"}

    async def close(self):
        pass


class MockSyncElasticsearch:
    """Mock for elasticsearch.Elasticsearch (sync client)."""

    def __init__(self):
        self._ping_result = True

    def ping(self, *args, **kwargs) -> bool:
        return self._ping_result

    def index(self, index: str, body: dict, **kwargs) -> dict:
        return {"result": "created", "_id": "test-id"}

    def search(self, index: str, body: dict, **kwargs) -> dict:
        return {
            "hits": {
                "total": {"value": 0},
                "hits": [],
            }
        }

    def close(self):
        pass
