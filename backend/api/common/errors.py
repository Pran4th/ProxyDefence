from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from backend.api.common.schema import APIErrorDetail, APIErrorResponse


def error_response(
    code: str = "INTERNAL_ERROR",
    message: str = "Internal server error",
    details: list[str] | None = None,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    request_id: str | None = None,
) -> HTTPException:
    detail = APIErrorDetail(code=code, message=message, details=details or [])
    body = APIErrorResponse(
        request_id=request_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        error=detail,
    )
    return HTTPException(status_code=status_code, detail=body.model_dump())


def error_response_invalid(
    message: str = "Invalid request",
    details: list[str] | None = None,
    request_id: str | None = None,
) -> HTTPException:
    return error_response(
        code="INVALID_REQUEST",
        message=message,
        details=details,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        request_id=request_id,
    )
