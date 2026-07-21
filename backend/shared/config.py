import os
from pathlib import Path


def _load_dotenv():
    """Load .env from repo root into os.environ if present and not already set.

    This makes local development work without manually exporting every variable.
    Docker/production environments set these vars through Docker Compose or
    the container runtime, so the .env file is never needed there.
    """
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if len(value) > 1 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value


_load_dotenv()

SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
GIT_COMMIT = os.getenv("GIT_COMMIT", "unknown")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _required_jwt_secret() -> str:
    """Return the JWT secret and reject template-grade values outside local development.

    Local development may still use a deliberately supplied short test secret so
    isolated unit tests remain simple. Staging and production must fail closed
    rather than silently issuing tokens with the example value.
    """
    value = _required_env("JWT_SECRET_KEY")
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    placeholder_values = {"change-me", "replace-me", "secret", "password"}
    if environment in {"staging", "production"} and (
        len(value) < 32 or value.strip().lower() in placeholder_values
    ):
        raise RuntimeError(
            "JWT_SECRET_KEY must be a unique, high-entropy secret of at least "
            "32 characters when ENVIRONMENT is staging or production"
        )
    return value
