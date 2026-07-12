from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.api.auth.schema import (
    RegisterRequest,
    LoginRequest,
    ProfileUpdateRequest,
    NotificationPreferencesRequest,
    ChangePasswordRequest,
)
from backend.api.auth.service import AuthService
from backend.api_service.rate_limit import limiter
from backend.api_service.security import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

_PROFILE_FIELDS = "id, email, username, role, organization, location, notification_preferences, tier, created_at"


def _serialize_user(user: dict) -> dict:
    """asyncpg doesn't auto-decode jsonb on this pool, so notification_preferences
    comes back as a raw JSON string unless parsed here."""
    import json
    result = dict(user)
    prefs = result.get("notification_preferences")
    if isinstance(prefs, str):
        result["notification_preferences"] = json.loads(prefs)
    return result


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
    return _serialize_user(user)


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
    return _serialize_user(user)


@router.patch("/me/notifications")
async def update_notification_preferences(
    payload: NotificationPreferencesRequest, request: Request, current_user: dict = Depends(get_current_user)
):
    import json

    async with request.app.state.pg_pool.acquire() as conn:
        user = await conn.fetchrow(
            f"""UPDATE users SET notification_preferences = $1::jsonb
                WHERE id = $2 RETURNING {_PROFILE_FIELDS}""",
            json.dumps(payload.model_dump()),
            current_user["id"],
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize_user(user)


@router.patch("/me/password")
@limiter.limit("5/minute")
async def change_password(
    payload: ChangePasswordRequest, request: Request, current_user: dict = Depends(get_current_user)
):
    service = AuthService(request.app.state.pg_pool)
    await service.change_password(current_user["id"], payload)
    return {"status": "password updated"}


@router.post("/me/tier/beta-toggle")
@limiter.limit("10/minute")
async def toggle_tier_beta(request: Request, current_user: dict = Depends(get_current_user)):
    """Free self-serve tier toggle for the beta -- no billing integration
    exists (or is planned for this pass), so this is an honest 'try
    Premium' switch rather than a fake purchase flow. Real payment
    processing is out of scope here by design."""
    async with request.app.state.pg_pool.acquire() as conn:
        user = await conn.fetchrow(
            f"""UPDATE users SET tier = CASE WHEN tier = 'premium' THEN 'free' ELSE 'premium' END
                WHERE id = $1 RETURNING {_PROFILE_FIELDS}""",
            current_user["id"],
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize_user(user)
