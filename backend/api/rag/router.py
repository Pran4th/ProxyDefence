from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from backend.api.rag.engine import RAGEngine
from backend.api.rag.retriever import Retriever

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])


class RAGQueryResponse(BaseModel):
    query: str
    context_text: str
    context_structured: list[dict]
    result_count: int


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:]
    return None


@router.get("/search", response_model=RAGQueryResponse)
async def rag_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=50),
) -> Any:
    engine = RAGEngine(retriever=Retriever(auth_token=_bearer_token(request)))
    result = await engine.retrieve_with_context(q, limit)
    return RAGQueryResponse(
        query=result["query"],
        context_text=result["context_text"],
        context_structured=result["context_structured"],
        result_count=result["result_count"],
    )
