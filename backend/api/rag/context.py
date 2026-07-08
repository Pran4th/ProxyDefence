from __future__ import annotations

from typing import Any

from backend.api.rag.retriever import RetrieverResult


class ContextAssembler:
    """Assembles retrieved documents into a structured context for LLM consumption."""

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    def assemble(self, results: list[RetrieverResult], query: str) -> str:
        if not results:
            return ""

        parts = [f"Context for query: {query}", ""]

        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] {r.title}")
            parts.append(f"Source: {r.source_type} ({r.source_id})")
            parts.append(f"Relevance: {r.score}")
            parts.append(r.text[:1000])
            parts.append("")

        return "\n".join(parts)

    def assemble_structured(self, results: list[RetrieverResult]) -> list[dict]:
        return [
            {
                "index": i,
                "title": r.title,
                "source_type": r.source_type,
                "source_id": r.source_id,
                "text": r.text[:1500],
                "relevance": r.score,
            }
            for i, r in enumerate(results, 1)
        ]
