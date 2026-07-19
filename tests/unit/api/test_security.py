"""Unit tests for API authentication and baseline browser-security controls."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.shared.request_middleware import RequestTrackingMiddleware


def test_request_tracking_middleware_adds_browser_security_headers():
    app = FastAPI()
    app.add_middleware(RequestTrackingMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    response = TestClient(app).get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(), geolocation=(), microphone=()"


class TestHashPassword:
    def test_returns_hash(self):
        from backend.api_service.security import hash_password
        hashed = hash_password("TestPass123!")
        assert isinstance(hashed, str)
        assert hashed != "TestPass123!"

    def test_same_password_different_hashes(self):
        from backend.api_service.security import hash_password
        h1 = hash_password("TestPass123!")
        h2 = hash_password("TestPass123!")
        assert h1 != h2


class TestVerifyPassword:
    def test_verifies_correct_password(self):
        from backend.api_service.security import hash_password, verify_password
        hashed = hash_password("TestPass123!")
        assert verify_password("TestPass123!", hashed) is True

    def test_rejects_incorrect_password(self):
        from backend.api_service.security import hash_password, verify_password
        hashed = hash_password("TestPass123!")
        assert verify_password("WrongPass!", hashed) is False


class TestCreateAccessToken:
    def test_returns_jwt_string(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_for_testing_only")
        monkeypatch.setenv("POSTGRES_USER", "x")
        monkeypatch.setenv("POSTGRES_PASSWORD", "x")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "x")

        import importlib
        from backend.shared import settings
        importlib.reload(settings)

        from backend.api_service.security import create_access_token
        token = create_access_token("42", {"role": "admin"})
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

    def test_token_can_be_decoded(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_for_testing_only")
        monkeypatch.setenv("POSTGRES_USER", "x")
        monkeypatch.setenv("POSTGRES_PASSWORD", "x")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "x")

        import importlib
        from backend.shared import settings
        importlib.reload(settings)
        from backend.api_service import security
        importlib.reload(security)

        from jose import jwt

        token = security.create_access_token("42", {"role": "analyst"})
        payload = jwt.decode(token, settings.settings.JWT_SECRET_KEY, algorithms=[settings.settings.JWT_ALGORITHM])
        assert payload["sub"] == "42"
        assert payload["role"] == "analyst"
