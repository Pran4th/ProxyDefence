from typing import Any

from pydantic import BaseModel


class EntityItem(BaseModel):
    entity: str
    type: str
    mentions: int
    avg_confidence: float


class EntityProfile(BaseModel):
    entity_text: str
    entity_type: str | None = None
    aliases: list[str] = []
    mention_frequency: int = 0
    risk_trend: Any = None
    last_seen: str | None = None
