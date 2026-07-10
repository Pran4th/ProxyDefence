"""Database-service configuration.

Re-exports shared settings so consumer.py / db.py / app.py continue to
import from ``config`` without scattering env-var lookups.
"""

from backend.shared.settings import settings

KAFKA_BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
POSTGRES_HOST = settings.POSTGRES_HOST
POSTGRES_PORT = settings.POSTGRES_PORT
POSTGRES_DB = settings.POSTGRES_DB
POSTGRES_USER = settings.POSTGRES_USER
POSTGRES_PASSWORD = settings.POSTGRES_PASSWORD
ELASTICSEARCH_HOST = settings.ELASTICSEARCH_HOST
ELASTICSEARCH_USER = settings.ELASTICSEARCH_USER
ELASTICSEARCH_PASSWORD = settings.ELASTICSEARCH_PASSWORD
JWT_SECRET_KEY = settings.JWT_SECRET_KEY
JWT_ALGORITHM = settings.JWT_ALGORITHM
