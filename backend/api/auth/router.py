from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.api.auth.schema import RegisterRequest, LoginRequest, ProfileUpdateRequest
from backend.api.auth.service import AuthService
from backend.api_service.rate_limit import limiter
from backend.api_service.security import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

_PROFILE_FIELDS = "id, email, username, role, organization, location, created_at"


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
            f"SELECT {_PROFILE_FIELDS} FROM users WHERE id = $1",
            current_user["id"],
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)


@router.patch("/me")
async def update_me(
    payload: ProfileUpdateRequest, request: Request, current_user: dict = Depends(get_current_user)
):
    async with request.app.state.pg_pool.acquire() as conn:
        user = await conn.fetchrow(
            f"""UPDATE users SET organization = $1, location = $2
                WHERE id = $3 RETURNING {_PROFILE_FIELDS}""",
            payload.organization,
            payload.location,
            current_user["id"],
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)
