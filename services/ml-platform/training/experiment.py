from typing import Any

try:
    import mlflow
    _MLFLOW_AVAILABLE = True
except ImportError:
    mlflow = None  # type: ignore
    _MLFLOW_AVAILABLE = False

from backend.shared.config import SERVICE_VERSION
from backend.shared.logging_config import get_logger
from config import MLFLOW_TRACKING_URI

logger = get_logger(__name__)


class ExperimentTracker:
    def __init__(self, tracking_uri: str | None = None,
                 experiment_name: str | None = None):
        self._tracking_uri = tracking_uri or MLFLOW_TRACKING_URI
        self._experiment_name = experiment_name or "ml-platform"
        self._run_id: str | None = None
        self._active = False

    def _ensure_experiment(self):
        if not _MLFLOW_AVAILABLE:
            raise ImportError("mlflow is not installed. Install research/requirements-research.txt")
        mlflow.set_tracking_uri(self._tracking_uri)
        existing = mlflow.get_experiment_by_name(self._experiment_name)
        if existing is None:
            mlflow.create_experiment(self._experiment_name)
        mlflow.set_experiment(self._experiment_name)

    def start_run(self, model_name: str, dataset_version: int | None = None,
                  feature_version: int | None = None,
                  git_commit: str | None = None):
        self._ensure_experiment()
        tags = {
            "model_name": model_name,
            "ml_platform.version": SERVICE_VERSION,
        }
        if dataset_version is not None:
            tags["dataset_version"] = str(dataset_version)
        if feature_version is not None:
            tags["feature_version"] = str(feature_version)
        if git_commit:
            tags["git_commit"] = git_commit

        run = mlflow.start_run(run_name=f"{model_name}_{dataset_version}", tags=tags)
        self._run_id = run.info.run_id
        self._active = True
        logger.info("mlflow run started", run_id=self._run_id)
        return self._run_id

    def log_params(self, params: dict[str, Any]):
        if self._active:
            mlflow.log_params(params)

    def log_metrics(self, metrics: dict[str, float]):
        if self._active:
            mlflow.log_metrics(metrics)

    def log_artifact(self, local_path: str):
        if self._active:
            mlflow.log_artifact(local_path)

    def log_dataset(self, dataset_path: str):
        if self._active:
            mlflow.log_input(
                mlflow.data.from_pandas(pd=None),  # placeholder for dataset reference
                context="training",
            )

    def set_tags(self, tags: dict[str, str]):
        if self._active:
            mlflow.set_tags(tags)

    def end_run(self):
        if self._active:
            mlflow.end_run()
            self._active = False
            logger.info("mlflow run ended", run_id=self._run_id)

    @property
    def run_id(self) -> str | None:
        return self._run_id
