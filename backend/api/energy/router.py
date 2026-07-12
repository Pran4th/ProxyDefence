import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response

from backend.api_service.security import decode_access_token
from backend.shared.settings import settings

router = APIRouter(prefix="/api/v1/energy", tags=["energy"])
intel_router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

ENERGY_BASE = settings.ENERGY_SERVICE_URL.rstrip("/")

# Deliberately empty: the response pipeline, digital twin, and SPR/procurement
# runs are the core product (and the hackathon judging path), not an add-on --
# gating them broke live demand for anyone not on the premium tier. Revisit
# premium/monetization scope once these engines are solid and it's not mid-hackathon.
# _check_premium below stays wired up so re-adding a path here is a one-line change.
PREMIUM_PATHS: set[str] = set()


async def _check_premium(request: Request) -> None:
    """_intel_proxy is registered via add_api_route on a catch-all path, so
    normal FastAPI Depends() can't gate individual proxied paths -- the token
    has to be pulled from the header and decoded by hand rather than via the
    get_current_user dependency (which relies on DI to resolve its
    HTTPBearer default)."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(auth_header[7:])
    user_id = int(payload["sub"])
    if payload.get("role") == "admin":
        return
    pool = request.app.state.pg_pool
    tier = await pool.fetchval("SELECT tier FROM users WHERE id = $1", user_id)
    if tier != "premium":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="This feature requires a Premium account.",
        )


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
    if path in PREMIUM_PATHS:
        await _check_premium(request)
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
