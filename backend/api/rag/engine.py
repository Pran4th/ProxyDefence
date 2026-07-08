from __future__ import annotations

from typing import Any

from backend.api.rag.context import ContextAssembler
from backend.api.rag.retriever import Retriever, RetrieverResult


class RAGEngine:
    """Orchestrates hybrid retrieval + context assembly for RAG-enabled agent responses."""

    def __init__(self, retriever: Retriever | None = None, context_assembler: ContextAssembler | None = None):
        self._retriever = retriever or Retriever()
        self._context_assembler = context_assembler or ContextAssembler()

    async def retrieve(self, query: str, limit: int = 10) -> list[RetrieverResult]:
        return await self._retriever.hybrid_search(query, limit)

    async def retrieve_with_context(self, query: str, limit: int = 10) -> dict:
        results = await self._retriever.hybrid_search(query, limit)
        context_text = self._context_assembler.assemble(results, query)
        context_structured = self._context_assembler.assemble_structured(results)
        return {
            "context_text": context_text,
            "context_structured": context_structured,
            "result_count": len(results),
            "query": query,
        }
