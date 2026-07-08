from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    entities: list[str] = Field(default_factory=list)


class WatchlistEntityAdd(BaseModel):
    entity_text: str = Field(min_length=1, max_length=500)
