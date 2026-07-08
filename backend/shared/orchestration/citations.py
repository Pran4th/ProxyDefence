from __future__ import annotations

from typing import Any


class CitationSource:
    """A structured citation from any source type."""

    def __init__(self, source_id: str, source_type: str, title: str, relevance: float = 1.0, url: str | None = None, snippet: str | None = None):
        self.source_id = source_id
        self.source_type = source_type
        self.title = title
        self.relevance = max(0.0, min(1.0, relevance))
        self.url = url
        self.snippet = snippet

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "title": self.title,
            "relevance": round(self.relevance, 2),
            "url": self.url,
            "snippet": self.snippet[:200] if self.snippet else None,
        }


class CitationEngine:
    """Centralized citation management. Collects citations from all sources and deduplicates them."""

    def __init__(self):
        self._sources: dict[str, CitationSource] = {}

    def add_article(self, article_id: str, title: str, relevance: float = 1.0, snippet: str | None = None) -> None:
        if article_id not in self._sources:
            self._sources[article_id] = CitationSource(
                source_id=article_id, source_type="article", title=title,
                relevance=relevance, snippet=snippet,
            )

    def add_entity(self, entity_name: str, entity_type: str, relevance: float = 1.0) -> None:
        key = f"entity:{entity_name}"
        if key not in self._sources:
            self._sources[key] = CitationSource(
                source_id=entity_name, source_type=f"entity:{entity_type}",
                title=entity_name, relevance=relevance,
            )

    def add_knowledge_graph(self, node_id: str, label: str, relevance: float = 1.0) -> None:
        key = f"kg:{node_id}"
        if key not in self._sources:
            self._sources[key] = CitationSource(
                source_id=node_id, source_type="knowledge_graph",
                title=label, relevance=relevance,
            )

    def add_simulation(self, run_id: str, scenario_name: str, relevance: float = 1.0) -> None:
        key = f"sim:{run_id}"
        if key not in self._sources:
            self._sources[key] = CitationSource(
                source_id=run_id, source_type="simulation",
                title=scenario_name, relevance=relevance,
            )

    def add_risk_record(self, signal_id: str, title: str, relevance: float = 1.0) -> None:
        key = f"risk:{signal_id}"
        if key not in self._sources:
            self._sources[key] = CitationSource(
                source_id=signal_id, source_type="risk_signal",
                title=title, relevance=relevance,
            )

    def add_procurement(self, run_id: str, title: str, relevance: float = 1.0) -> None:
        key = f"proc:{run_id}"
        if key not in self._sources:
            self._sources[key] = CitationSource(
                source_id=run_id, source_type="procurement",
                title=title, relevance=relevance,
            )

    def add_spr(self, facility_id: str, name: str, relevance: float = 1.0) -> None:
        key = f"spr:{facility_id}"
        if key not in self._sources:
            self._sources[key] = CitationSource(
                source_id=facility_id, source_type="spr",
                title=name, relevance=relevance,
            )

    def add_custom(self, source_id: str, source_type: str, title: str, relevance: float = 1.0, url: str | None = None, snippet: str | None = None) -> None:
        if source_id not in self._sources:
            self._sources[source_id] = CitationSource(
                source_id=source_id, source_type=source_type,
                title=title, relevance=relevance, url=url, snippet=snippet,
            )

    def get_all(self, min_relevance: float = 0.0, max_count: int = 20) -> list[dict]:
        sorted_sources = sorted(self._sources.values(), key=lambda s: s.relevance, reverse=True)
        return [s.to_dict() for s in sorted_sources if s.relevance >= min_relevance][:max_count]

    def merge(self, other: "CitationEngine") -> None:
        for sid, source in other._sources.items():
            if sid not in self._sources:
                self._sources[sid] = source
            else:
                existing = self._sources[sid]
                existing.relevance = max(existing.relevance, source.relevance)
                if source.snippet and not existing.snippet:
                    existing.snippet = source.snippet

    def clear(self) -> None:
        self._sources.clear()

    @property
    def count(self) -> int:
        return len(self._sources)

    def to_agent_response(self) -> list[dict]:
        return self.get_all(min_relevance=0.3)
