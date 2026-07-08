from typing import Any

from pydantic import BaseModel


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: list[dict[str, Any]]
