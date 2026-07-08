from typing import Any, Optional

from pydantic import BaseModel


class APIErrorDetail(BaseModel):
    code: str
    message: str
    details: list[str] = []


class APIErrorResponse(BaseModel):
    success: bool = False
    request_id: Optional[str] = None
    timestamp: str = ""
    error: APIErrorDetail


def record_to_dict(record: Any) -> dict[str, Any]:
    item = dict(record)
    for key, value in list(item.items()):
        if hasattr(value, "isoformat"):
            item[key] = value.isoformat()
    return item
