from typing import Any

from pydantic import BaseModel


class EventItem(BaseModel):
    id: int
    title: str | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    last_seen: str | None = None
    topic: str | None = None
    entities: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
