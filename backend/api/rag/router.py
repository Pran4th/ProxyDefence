from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.api.rag.engine import RAGEngine

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])


class RAGQueryResponse(BaseModel):
    query: str
    context_text: str
    context_structured: list[dict]
    result_count: int


@router.get("/search", response_model=RAGQueryResponse)
async def rag_search(q: str = Query(..., min_length=1, max_length=500), limit: int = Query(default=10, ge=1, le=50)) -> Any:
    engine = RAGEngine()
    result = await engine.retrieve_with_context(q, limit)
    return RAGQueryResponse(
        query=result["query"],
        context_text=result["context_text"],
        context_structured=result["context_structured"],
        result_count=result["result_count"],
    )
