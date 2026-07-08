"""Connector exception hierarchy."""


class ConnectorError(Exception):
    """Base exception for all connector errors."""


class ConnectorConnectionError(ConnectorError):
    """Raised when a connection to a data source fails."""


class ConnectorAuthError(ConnectorError):
    """Raised when authentication with a data source fails."""


class ConnectorSchemaDiscoveryError(ConnectorError):
    """Raised when schema discovery fails."""


class ConnectorFetchError(ConnectorError):
    """Raised when data fetching fails."""


class ConnectorValidationError(ConnectorError):
    """Raised when connector validation fails."""


class ConnectorRateLimitError(ConnectorError):
    """Raised when rate limit is exceeded."""


class ConnectorCheckpointError(ConnectorError):
    """Raised when checkpoint operations fail."""
