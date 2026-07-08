from typing import Any

from fastapi import Request

from backend.api_service.security import get_current_user as _get_current_user
from backend.api_service.security import require_admin as _require_admin


async def get_pool(request: Request) -> Any:
    return request.app.state.pg_pool


async def get_es(request: Request) -> Any:
    return request.app.state.es_client


get_current_user = _get_current_user
require_admin = _require_admin
