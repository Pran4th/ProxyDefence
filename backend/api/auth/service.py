from fastapi import HTTPException, status

from backend.api.auth.schema import RegisterRequest, LoginRequest
from backend.api_service.security import create_access_token, hash_password, verify_password


class AuthService:
    def __init__(self, pool):
        self.pool = pool

    async def register(self, payload: RegisterRequest) -> dict:
        async with self.pool.acquire() as conn:
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

    async def login(self, payload: LoginRequest) -> dict:
        async with self.pool.acquire() as conn:
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
