import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.api.copilot.repository import CopilotRepository
from backend.api.copilot.schema import CopilotQuery, ConversationCreate
from backend.api.copilot.service import CopilotService
from backend.api.common.errors import error_response
from backend.api_service.security import get_current_user
from backend.shared.llm.exceptions import LLMRateLimitError

router = APIRouter(prefix="/copilot", tags=["Copilot"])


@router.post("/query")
async def query_copilot(
    payload: CopilotQuery,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = CopilotRepository(request.app.state.pg_pool)
    service = CopilotService(repo)

    try:
        result = await service.query(payload.question, payload.conversation_id)
        return result
    except LLMRateLimitError:
        raise error_response(
            code="LLM_RATE_LIMITED",
            message="The LLM provider's rate limit was exceeded. Try again shortly.",
            status_code=503,
        )
    except Exception:
        raise error_response(code="COPILOT_ERROR", message="Copilot query processing failed", status_code=500)


@router.post("/query/stream")
async def query_copilot_stream(payload: CopilotQuery, request: Request):
    repo = CopilotRepository(request.app.state.pg_pool)
    service = CopilotService(repo)

    async def event_generator():
        try:
            async for event in service.query_stream(payload.question, payload.conversation_id):
                yield event
        except Exception as e:
            yield f'data: {{"type":"error","value":"{str(e)}"}}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/chat")
async def create_conversation(
    payload: ConversationCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = CopilotRepository(request.app.state.pg_pool)
    user_id = current_user.get("id") if isinstance(current_user, dict) else None
    conv_id = await repo.create_conversation(user_id, payload.title)
    return {"conversation_id": conv_id, "title": payload.title}


@router.get("/chat")
async def list_conversations(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    repo = CopilotRepository(request.app.state.pg_pool)
    user_id = current_user.get("id") if isinstance(current_user, dict) else 0
    conversations = await repo.get_conversations(user_id, limit)
    return {"conversations": conversations}


@router.get("/chat/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = CopilotRepository(request.app.state.pg_pool)
    messages = await repo.get_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}
