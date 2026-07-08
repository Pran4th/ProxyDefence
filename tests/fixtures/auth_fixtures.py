from datetime import datetime, timedelta, timezone

from jose import jwt

from backend.shared.settings import settings


def make_token(user_id: int, role: str = "analyst", expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(hours=1)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def make_expired_token(user_id: int = 1, role: str = "analyst") -> str:
    return make_token(user_id, role, expires_delta=timedelta(hours=-1))


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
