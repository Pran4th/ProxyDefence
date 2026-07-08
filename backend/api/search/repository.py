from typing import Any


class SearchRepository:
    def __init__(self, es_client) -> None:
        self.es_client = es_client

    async def search_articles(self, query: str, limit: int = 20) -> dict[str, Any]:
        response = await self.es_client.search(
            index="processed_articles",
            body={
                "size": limit,
                "query": {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title^3", "summary^2", "content", "source", "topic"],
                                    "type": "best_fields",
                                    "fuzziness": "AUTO",
                                }
                            },
                            {
                                "match_phrase": {
                                    "title": {"query": query, "boost": 4}
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "sort": ["_score", {"published_at": {"order": "desc", "unmapped_type": "date"}}],
            },
        )

        return {
            "query": query,
            "total_results": response['hits']['total']['value'],
            "results": [hit["_source"] for hit in response['hits']['hits']],
        }

    async def search_context(self, question: str, limit: int) -> list[dict[str, Any]]:
        response = await self.es_client.search(
            index="processed_articles",
            body={
                "size": limit,
                "query": {
                    "multi_match": {
                        "query": question,
                        "fields": ["title^3", "summary^2", "content", "source", "topic", "entities"],
                        "fuzziness": "AUTO",
                    }
                },
            },
        )
        return [hit["_source"] for hit in response["hits"]["hits"]]
