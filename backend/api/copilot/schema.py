from pydantic import BaseModel, Field


class CopilotQuery(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: int | None = None


class ConversationCreate(BaseModel):
    title: str = Field(default="New Chat", max_length=200)


class SaveToCaseRequest(BaseModel):
    case_id: int
    question: str = Field(min_length=1, max_length=1000)
    answer: dict
