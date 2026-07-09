from typing import Any


class SearchRepository:
    def __init__(self, es_client) -> None:
        self.es_client = es_client

    async def search_articles(
        self,
        query: str,
        topic: str | None = None,
        risk_level: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters: list[dict[str, Any]] = []
        if topic:
            filters.append({"term": {"topic": topic}})
        if risk_level:
            filters.append({"term": {"risk_level": risk_level}})

        response = await self.es_client.search(
            index="processed_articles",
            body={
                "size": limit,
                "from": offset,
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
                        "filter": filters,
                    }
                },
                "highlight": {
                    "fields": {
                        "title": {},
                        "summary": {},
                    },
                    "pre_tags": ["<mark>"],
                    "post_tags": ["</mark>"],
                },
                "sort": ["_score", {"published_at": {"order": "desc", "unmapped_type": "date"}}],
            },
        )

        return {
            "query": query,
            "total_results": response["hits"]["total"]["value"],
            "results": [
                {**hit["_source"], "_highlight": hit.get("highlight", {})}
                for hit in response["hits"]["hits"]
            ],
            "limit": limit,
            "offset": offset,
        }
