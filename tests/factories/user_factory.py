import uuid


def build_user(**overrides) -> dict:
    user = {
        "email": f"user{uuid.uuid4().hex[:8]}@test.local",
        "username": f"testuser_{uuid.uuid4().hex[:6]}",
        "password": "TestPass123!",
        "role": "analyst",
    }
    user.update(overrides)
    return user


def build_admin(**overrides) -> dict:
    user = build_user(role="admin", **overrides)
    return user


def build_login_payload(email: str | None = None, password: str | None = None) -> dict:
    return {
        "email": email or "admin@defenseintel.local",
        "password": password or "AdminPass123!",
    }
