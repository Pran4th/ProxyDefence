from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.api_service.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request):
    async with request.app.state.pg_pool.acquire() as conn:
        existing_user = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1 OR username = $2",
            payload.email.lower(),
            payload.username.lower(),
        )
        if existing_user:
            raise HTTPException(status_code=409, detail="User already exists")

        user = await conn.fetchrow(
            """
            INSERT INTO users (email, username, password_hash, role)
            VALUES ($1, $2, $3, 'analyst')
            RETURNING id, email, username, role, created_at
            """,
            payload.email.lower(),
            payload.username.lower(),
            hash_password(payload.password),
        )

    token = create_access_token(str(user["id"]), {"role": user["role"]})
    return {"access_token": token, "token_type": "bearer", "user": dict(user)}


@router.post("/login")
async def login(payload: LoginRequest, request: Request):
    async with request.app.state.pg_pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, email, username, role, created_at, password_hash
            FROM users
            WHERE email = $1
            """,
            payload.email.lower(),
        )

    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user["id"]), {"role": user["role"]})
    user_payload = {key: value for key, value in dict(user).items() if key != "password_hash"}
    return {"access_token": token, "token_type": "bearer", "user": user_payload}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
