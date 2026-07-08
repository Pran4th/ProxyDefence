from typing import Any

from pydantic import BaseModel, Field


class ReportContextParams(BaseModel):
    topic: str | None = None
    entity: str | None = None
    event_id: int | None = None
    limit: int = Field(default=10, ge=1, le=100)
