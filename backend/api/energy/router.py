import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

from backend.shared.settings import settings

router = APIRouter(prefix="/api/v1/energy", tags=["energy"])
intel_router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

ENERGY_BASE = settings.ENERGY_SERVICE_URL.rstrip("/")


async def _proxy(request: Request, path: str):
    url = f"{ENERGY_BASE}/api/v1/energy/{path}"
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length"}
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            params=request.query_params,
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


async def _intel_proxy(request: Request, path: str):
    url = f"{ENERGY_BASE}/api/v1/intelligence/{path}"
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length"}
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            params=request.query_params,
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
    router.add_api_route(
        path="/{path:path}",
        endpoint=_proxy,
        methods=[method],
        name=f"proxy_{method.lower()}",
    )
    intel_router.add_api_route(
        path="/{path:path}",
        endpoint=_intel_proxy,
        methods=[method],
        name=f"intel_proxy_{method.lower()}",
    )
