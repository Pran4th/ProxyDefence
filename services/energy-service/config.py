"""Energy-service configuration.

Re-exports shared PostgreSQL settings so local ``db.py`` and routers
never reach directly for ``os.getenv``.
"""

from backend.shared.settings import settings

POSTGRES_PORT = settings.POSTGRES_PORT
POSTGRES_HOST = settings.POSTGRES_HOST
POSTGRES_DB = settings.POSTGRES_DB
POSTGRES_USER = settings.POSTGRES_USER
POSTGRES_PASSWORD = settings.POSTGRES_PASSWORD
