from pydantic import BaseModel, Field


class PageParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ReportGenerateRequest(BaseModel):
    title: str = Field(default="Geopolitical Intelligence Brief", min_length=3, max_length=200)
    topic: str | None = None
    entity: str | None = None
    event_id: int | None = None
    limit: int = Field(default=10, ge=1, le=25)


class WatchlistCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    entities: list[str] = Field(default_factory=list)


class AlertCreateRequest(BaseModel):
    watchlist_id: int | None = None
    entity_text: str | None = None
    event_id: int | None = None
    alert_type: str = Field(default="manual", max_length=50)
    message: str = Field(min_length=3)
    risk_score: float = Field(default=0, ge=0, le=100)


class CopilotQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)

