from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class ExecutionError(Exception):
    """Base exception for all execution-related errors."""


class StageExecutionError(ExecutionError):
    """Raised when a pipeline stage fails during execution."""


class PipelineExecutionError(ExecutionError):
    """Raised when an entire pipeline execution fails."""


class ConfigurationError(ExecutionError):
    """Raised when execution configuration is invalid."""


class ExecutionCancelledError(ExecutionError):
    """Raised when execution is cancelled."""


class StageNotFoundError(ExecutionError):
    """Raised when a requested stage type is not found in the registry."""


class DependencyError(ExecutionError):
    """Raised when stage dependency resolution fails."""
