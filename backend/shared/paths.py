"""Canonical path resolution for the ProxyDefence monorepo.

Eliminates duplicated ``os.path.join(os.path.dirname(__file__), …)``
chains that litter the service codebase.
"""

from pathlib import Path


def project_root() -> Path:
    """Return the absolute path to the repository root.

    Relies on ``.env`` or its git-tracked template ``.env.example`` being
    present at the root -- ``.env`` itself is gitignored, so a fresh CI
    checkout only has the template.
    """
    candidate = Path(__file__).resolve().parent.parent.parent
    if (candidate / ".env").exists() or (candidate / ".env.example").exists():
        return candidate
    raise RuntimeError(
        f"Could not locate project root via .env/.env.example sentinel (tried {candidate})"
    )


def infra_sql(schema_name: str | None = None) -> Path:
    """Return the path to a canonical schema SQL file under ``infra/sql/``.

    If *schema_name* is *None* returns the ``infra/sql/`` directory itself.
    """
    base = project_root() / "infra" / "sql"
    if schema_name is None:
        return base
    return base / f"{schema_name}_schema.sql"


def service_dir(service_name: str) -> Path:
    """Return the path to a service directory under ``services/``."""
    return project_root() / "services" / service_name
