from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.api.auth.schema import RegisterRequest, LoginRequest
from backend.api.auth.service import AuthService
from backend.api_service.rate_limit import limiter
from backend.api_service.security import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(payload: RegisterRequest, request: Request):
    service = AuthService(request.app.state.pg_pool)
    return await service.register(payload)


@router.post("/login")
@limiter.limit("20/minute")
async def login(payload: LoginRequest, request: Request):
    service = AuthService(request.app.state.pg_pool)
    return await service.login(payload)


@router.get("/me")
async def me(request: Request, current_user: dict = Depends(get_current_user)):
    async with request.app.state.pg_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, email, username, role, created_at FROM users WHERE id = $1",
            current_user["id"],
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)
