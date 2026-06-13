from __future__ import annotations

from statistics import mean
from typing import Any

from backend.api_service.dto import (
    AlertCreateRequest,
    CopilotQueryRequest,
    ReportGenerateRequest,
    WatchlistCreateRequest,
)
from backend.api_service.repositories.intelligence import IntelligenceRepository
from backend.api_service.services.cache import cache


class IntelligenceService:
    def __init__(self, pool: Any, es_client: Any | None = None):
        self.repository = IntelligenceRepository(pool)
        self.es_client = es_client

    async def list_events(self, limit: int, offset: int) -> list[dict[str, Any]]:
        cache_key = f"events:{limit}:{offset}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        events = await self.repository.list_events(limit=limit, offset=offset)
        cache.set(cache_key, events, ttl_seconds=30)
        return events

    async def get_event(self, event_id: int) -> dict[str, Any] | None:
        cache_key = f"event:{event_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        event = await self.repository.get_event(event_id)
        if event is not None:
            cache.set(cache_key, event, ttl_seconds=60)
        return event

    async def get_event_articles(self, event_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.repository.get_event_articles(event_id=event_id, limit=limit, offset=offset)

    async def get_entity_profile(self, entity: str) -> dict[str, Any] | None:
        profile = await self.repository.get_entity_profile(entity)
        if profile is None:
            return None

        timeline = await self.repository.get_entity_timeline(entity)
        profile["timeline_preview"] = timeline[:10]
        return profile

    async def get_entity_timeline(self, entity: str) -> list[dict[str, Any]]:
        return await self.repository.get_entity_timeline(entity)

    async def generate_report(self, request: ReportGenerateRequest, user_id: int | None) -> dict[str, Any]:
        context = await self.repository.get_report_context(
            topic=request.topic,
            entity=request.entity,
            event_id=request.event_id,
            limit=request.limit,
        )
        report_payload = self._build_report_payload(request, context)
        report_payload["created_by"] = user_id
        report = await self.repository.create_report(report_payload)
        await self.repository.audit(user_id, "report.generate", "reports", {"report_id": report["id"]})
        return report

    async def create_watchlist(self, request: WatchlistCreateRequest, user_id: int | None) -> dict[str, Any]:
        watchlist = await self.repository.create_watchlist(
            name=request.name,
            description=request.description,
            owner_id=user_id,
            entities=request.entities,
        )
        await self.repository.audit(user_id, "watchlist.create", "watchlists", {"watchlist_id": watchlist["id"]})
        return watchlist

    async def list_watchlists(self, user_id: int | None, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.repository.list_watchlists(owner_id=user_id, limit=limit, offset=offset)

    async def create_alert(self, request: AlertCreateRequest, user_id: int | None) -> dict[str, Any]:
        alert = await self.repository.create_alert(request.model_dump())
        await self.repository.audit(user_id, "alert.create", "alerts", {"alert_id": alert["id"]})
        return alert

    async def get_timeline(
        self,
        entity: str | None,
        event_id: int | None,
        timeline_type: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        return await self.repository.get_timeline(
            entity=entity,
            event_id=event_id,
            timeline_type=timeline_type,
            limit=limit,
        )

    async def answer_copilot_query(self, request: CopilotQueryRequest, user_id: int | None) -> dict[str, Any]:
        context = await self.repository.search_context(
            es_client=self.es_client,
            question=request.question,
            limit=request.limit,
        )
        answer = self._build_copilot_answer(request.question, context)
        await self.repository.audit(user_id, "copilot.query", "copilot", {"citations": len(answer["citations"])})
        return answer

    async def expand_graph(self, entity: str, depth: int, limit: int) -> dict[str, Any]:
        return await self.repository.expand_graph(entity=entity, depth=depth, limit=limit)

    def _build_report_payload(
        self,
        request: ReportGenerateRequest,
        context: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        articles = context["articles"]
        events = context["events"]

        threat_scores = [float(article.get("threat_score") or 0) for article in articles]
        confidence_scores = [float(article.get("confidence") or 0) for article in articles]
        avg_threat = round(mean(threat_scores), 2) if threat_scores else 0.0
        confidence = round(mean(confidence_scores), 2) if confidence_scores else 0.0
        actors = self._extract_key_actors(context["entities"])

        subject = request.topic or request.entity or (events[0]["title"] if events else "current intelligence picture")
        executive_summary = (
            f"Analysis of {subject} is based on {len(articles)} source articles and "
            f"{len(events)} correlated events. Current aggregate risk is {avg_threat}/100."
        )
        key_events = [
            {
                "id": event["id"],
                "title": event["title"],
                "topic": event.get("topic"),
                "risk_score": event.get("risk_score"),
                "article_count": event.get("article_count"),
            }
            for event in events
        ]
        threat_assessment = self._threat_assessment(avg_threat, actors, key_events)
        recommendations = self._recommendations(avg_threat, actors)

        return {
            "title": f"Intelligence Report: {subject}",
            "topic": request.topic,
            "entity": request.entity,
            "event_id": request.event_id,
            "executive_summary": executive_summary,
            "key_actors": actors,
            "key_events": key_events,
            "threat_assessment": threat_assessment,
            "confidence_score": confidence,
            "recommendations": recommendations,
            "source_article_ids": [article["id"] for article in articles],
        }

    def _build_copilot_answer(self, question: str, context: list[dict[str, Any]]) -> dict[str, Any]:
        if not context:
            return {
                "question": question,
                "answer": "No matching intelligence sources were found for this question.",
                "citations": [],
                "confidence_score": 0.0,
            }

        citations = [
            {
                "article_id": item.get("id"),
                "title": item.get("title"),
                "source": item.get("source"),
                "published_at": item.get("published_at"),
                "url": item.get("url"),
            }
            for item in context
        ]
        top_titles = "; ".join(str(item.get("title")) for item in context[:3] if item.get("title"))
        avg_confidence = round(mean(float(item.get("confidence") or 0) for item in context), 2)
        avg_risk = round(mean(float(item.get("threat_score") or 0) for item in context), 2)

        answer = (
            f"Based on the retrieved intelligence, the strongest signals related to this question are: "
            f"{top_titles}. The cited source set has an average threat score of {avg_risk}/100. "
            "Use the citations to inspect the underlying articles before making operational decisions."
        )
        return {
            "question": question,
            "answer": answer,
            "citations": citations,
            "confidence_score": avg_confidence,
        }

    def _extract_key_actors(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        actors: dict[str, dict[str, Any]] = {}
        for row in entities:
            entity = row.get("entity_text")
            if not entity:
                continue
            actors[entity] = {
                "entity": entity,
                "entity_type": row.get("entity_type"),
                "mentions": int(row.get("mentions") or 0),
            }
        return sorted(actors.values(), key=lambda item: item["mentions"], reverse=True)[:10]

    def _threat_assessment(
        self,
        avg_threat: float,
        actors: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> str:
        actor_names = ", ".join(actor["entity"] for actor in actors[:5]) or "no dominant actors"
        if avg_threat >= 75:
            posture = "Critical risk posture with immediate monitoring recommended"
        elif avg_threat >= 50:
            posture = "Elevated risk posture requiring analyst review"
        elif avg_threat >= 25:
            posture = "Moderate risk posture with developing indicators"
        else:
            posture = "Low current risk posture"
        return f"{posture}. Key actors: {actor_names}. Correlated events reviewed: {len(events)}."

    def _recommendations(self, avg_threat: float, actors: list[dict[str, Any]]) -> list[str]:
        recommendations = [
            "Continue monitoring cited source articles for corroboration and timeline changes.",
            "Validate high-impact claims with at least two independent sources before escalation.",
        ]
        if actors:
            recommendations.append(f"Add {actors[0]['entity']} to analyst watchlists if not already tracked.")
        if avg_threat >= 50:
            recommendations.append("Escalate to a human analyst for threat assessment and stakeholder briefing.")
        return recommendations
