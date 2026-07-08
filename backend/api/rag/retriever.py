from __future__ import annotations

from typing import Any

import httpx

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class RetrieverResult:
    def __init__(self, text: str, source_id: str, source_type: str, title: str, score: float, metadata: dict | None = None):
        self.text = text
        self.source_id = source_id
        self.source_type = source_type
        self.title = title
        self.score = score
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "title": self.title,
            "score": self.score,
            "metadata": self.metadata,
        }


class Retriever:
    """Hybrid retriever combining dense (pgvector), sparse (ES BM25), and knowledge graph expansion."""

    def __init__(self, modular_api_url: str = "http://localhost:8000", embedding_service_url: str = "http://localhost:8005"):
        self.modular_api_url = modular_api_url
        self.embedding_service_url = embedding_service_url

    async def dense_retrieval(self, query: str, limit: int = 10) -> list[RetrieverResult]:
        async with httpx.AsyncClient(base_url=self.modular_api_url) as client:
            try:
                resp = await client.get("/semantic-search", params={"q": query, "limit": limit}, timeout=15)
                resp.raise_for_status()
                data = resp.json() if isinstance(resp.json(), list) else resp.json().get("results", [])
                return [
                    RetrieverResult(
                        text=item.get("content", item.get("text", "")),
                        source_id=str(item.get("id", "")),
                        source_type="article",
                        title=item.get("title", ""),
                        score=item.get("score", item.get("similarity", 0.0)),
                    )
                    for item in data
                ]
            except Exception as e:
                logger.warning("Dense retrieval failed: %s", e)
                return []

    async def sparse_retrieval(self, query: str, limit: int = 10) -> list[RetrieverResult]:
        async with httpx.AsyncClient(base_url=self.modular_api_url) as client:
            try:
                resp = await client.get("/search", params={"q": query, "limit": limit}, timeout=15)
                resp.raise_for_status()
                data = resp.json() if isinstance(resp.json(), list) else resp.json().get("results", [])
                return [
                    RetrieverResult(
                        text=item.get("content", item.get("text", "")),
                        source_id=str(item.get("id", "")),
                        source_type="article",
                        title=item.get("title", ""),
                        score=item.get("score", item.get("_score", 0.0)),
                    )
                    for item in data
                ]
            except Exception as e:
                logger.warning("Sparse retrieval failed: %s", e)
                return []

    async def kg_expansion(self, query: str, limit: int = 10) -> list[RetrieverResult]:
        async with httpx.AsyncClient(base_url=self.modular_api_url) as client:
            try:
                resp = await client.get("/graph/network", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                nodes = data.get("nodes", []) if isinstance(data, dict) else []
                return [
                    RetrieverResult(
                        text=f"{n.get('label', n.get('name', ''))}: {n.get('description', n.get('type', ''))}",
                        source_id=str(n.get("id", "")),
                        source_type="knowledge_graph",
                        title=n.get("label", n.get("name", "Unknown")),
                        score=n.get("relevance", 0.5),
                        metadata={"type": n.get("type", ""), "group": n.get("group", "")},
                    )
                    for n in nodes[:limit]
                    if query.lower() in n.get("label", "").lower() or query.lower() in n.get("name", "").lower()
                ]
            except Exception as e:
                logger.warning("KG expansion failed: %s", e)
                return []

    async def hybrid_search(self, query: str, limit: int = 10) -> list[RetrieverResult]:
        dense_results = await self.dense_retrieval(query, limit)
        sparse_results = await self.sparse_retrieval(query, limit)
        kg_results = await self.kg_expansion(query, limit)

        all_results = self._rrf_fusion(dense_results, sparse_results, kg_results)
        return all_results[:limit]

    def _rrf_fusion(self, *result_lists: list[RetrieverResult], k: int = 60) -> list[RetrieverResult]:
        scores: dict[str, dict] = {}
        for rank, results in enumerate(result_lists):
            for i, r in enumerate(results):
                key = r.source_id
                if key not in scores:
                    scores[key] = {"result": r, "rrf_score": 0.0}
                scores[key]["rrf_score"] += 1.0 / (k + i + 1)

        sorted_results = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
        for entry in sorted_results:
            entry["result"].score = round(entry["rrf_score"], 4)

        return [entry["result"] for entry in sorted_results]
