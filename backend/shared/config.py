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
