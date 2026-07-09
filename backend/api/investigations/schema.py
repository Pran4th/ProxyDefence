from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    priority: str = Field(default="medium")


class CaseItemAdd(BaseModel):
    item_type: str = Field(min_length=1, max_length=50)
    item_id: int


class CaseNoteAdd(BaseModel):
    note: str = Field(min_length=3, max_length=5000)
