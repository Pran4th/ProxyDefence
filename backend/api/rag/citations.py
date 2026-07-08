from __future__ import annotations

from typing import Any


class CitationFormatter:
    """Formats retrieval results into citation objects for the agent response."""

    @staticmethod
    def format_sources(results: list[dict], max_sources: int = 5) -> list[dict]:
        seen = set()
        citations = []
        for r in results:
            cid = str(r.get("source_id", ""))
            if cid in seen:
                continue
            seen.add(cid)
            citations.append({
                "source_id": cid,
                "source_type": r.get("source_type", "article"),
                "title": r.get("title", "Untitled"),
                "relevance": r.get("relevance", r.get("score", 0.0)),
                "snippet": r.get("text", "")[:200],
            })
            if len(citations) >= max_sources:
                break
        return citations
