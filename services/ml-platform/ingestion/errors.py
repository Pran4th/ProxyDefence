class IngestionError(Exception):
    """Base exception for all ingestion pipeline errors."""


class IngestionStepError(IngestionError):
    """Raised when a pipeline step fails during execution."""


class IngestionPipelineError(IngestionError):
    """Raised when pipeline validation or execution fails."""


class IngestionTimeoutError(IngestionError):
    """Raised when a pipeline step exceeds its timeout."""


class IngestionConfigError(IngestionError):
    """Raised when pipeline configuration is invalid."""


class IngestionScheduleError(IngestionError):
    """Raised when the scheduler encounters an error."""


class IngestionCancelledError(IngestionError):
    """Raised when execution is cancelled by the user."""
