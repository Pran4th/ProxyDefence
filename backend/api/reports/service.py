from typing import Any

from backend.api.reports.repository import ReportRepository


class ReportService:
    def __init__(self, repository: ReportRepository) -> None:
        self.repository = repository

    async def list_reports(self, limit: int, offset: int, created_by: int | None = None) -> list[dict[str, Any]]:
        return await self.repository.list_reports(limit, offset, created_by)

    async def get_report(self, report_id: int, created_by: int | None = None) -> dict[str, Any] | None:
        return await self.repository.get_report(report_id, created_by)

    async def get_report_context(
        self, topic: str | None, entity: str | None, event_id: int | None, limit: int
    ) -> dict[str, Any]:
        return await self.repository.get_report_context(topic, entity, event_id, limit)

    async def generate_case_report(self, case_id: int, created_by: int | None = None) -> dict[str, Any]:
        data = await self.repository.load_case_report_data(case_id)
        case = data["case"]
        events = data["events"]
        alerts = data["alerts"]
        entities = data["entities"]
        articles = data["articles"]

        executive_summary = self._build_executive_summary(case, events, alerts, entities)
        key_actors = self._build_key_actors(entities, alerts)
        key_events = self._build_key_events(events)
        threat_assessment = self._build_threat_assessment(events, alerts)
        recommendations = self._build_recommendations()
        confidence_score = self._build_confidence_score(events)
        source_article_ids = [article["id"] for article in articles]

        report_payload = {
            "title": f"Intelligence Brief - {case['title']}",
            "executive_summary": executive_summary,
            "key_actors": key_actors,
            "key_events": key_events,
            "threat_assessment": threat_assessment,
            "confidence_score": confidence_score,
            "recommendations": recommendations,
            "source_article_ids": source_article_ids,
            "created_by": created_by,
        }

        return await self.repository.create_report(report_payload)

    def _build_executive_summary(self, case: Any, events: list, alerts: list, entities: list) -> str:
        event_count = len(events)
        alert_count = len(alerts)
        entity_list = ", ".join([e["entity_text"] for e in entities[:3]])

        summary = f"Investigation '{case['title']}' contains {alert_count} alerts across {event_count} events"
        if entity_list:
            summary += f" involving {entity_list}"
        summary += "."
        return summary

    def _build_key_actors(self, entities: list, alerts: list) -> list[dict]:
        key_actors = []
        for entity in entities[:5]:
            key_actors.append({
                "name": entity["entity_text"],
                "type": entity["entity_type"],
                "mentions": entity["mention_count"],
            })
        return key_actors

    def _build_key_events(self, events: list) -> list[dict]:
        key_events = []
        for event in events:
            key_events.append({
                "id": event["id"],
                "title": event["title"],
                "risk_score": float(event["risk_score"] or 0),
                "risk_level": event["risk_level"],
            })
        return key_events

    def _build_threat_assessment(self, events: list, alerts: list) -> str:
        if not events and not alerts:
            return "Insufficient data for threat assessment."
        max_risk = 0
        if events:
            max_risk = max(e["risk_score"] or 0 for e in events)
        if alerts:
            alert_risks = [a["risk_score"] or 0 for a in alerts]
            if alert_risks:
                max_risk = max(max_risk, max(alert_risks))
        if max_risk >= 75:
            return "Critical threat activity detected."
        elif max_risk >= 50:
            return "Elevated threat activity detected."
        else:
            return "Low to moderate threat activity."

    def _build_recommendations(self) -> list[str]:
        return [
            "Continue monitoring watchlists for related entities",
            "Review all associated events for patterns",
            "Escalate if risk score increases",
            "Cross-reference with related investigations",
        ]

    def _build_confidence_score(self, events: list) -> float:
        if not events:
            return 50.0
        confidences = [e["confidence"] for e in events if e["confidence"] is not None]
        if not confidences:
            return 50.0
        return float(sum(confidences) / len(confidences))
