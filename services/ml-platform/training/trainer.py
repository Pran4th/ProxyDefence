import time
from pathlib import Path
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR, DATASET_DIR
from db import get_pool
from training.models import MODEL_REGISTRY, REGRESSION_MODEL_REGISTRY, BaseModelWrapper
from training.experiment import ExperimentTracker
from evaluation.classification import evaluate_classification
from evaluation.regression import evaluate_regression

logger = get_logger(__name__)


def _scalar_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    return {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


class ModelTrainer:
    def __init__(self, model_type: str, parameters: dict[str, Any] | None = None,
                 random_seed: int = 42, task: str = "classification"):
        if task == "classification":
            registry = MODEL_REGISTRY
        elif task == "regression":
            registry = REGRESSION_MODEL_REGISTRY
        else:
            raise ValueError(f"Unknown task: {task}. Available: classification, regression")
        if model_type not in registry:
            raise ValueError(f"Unknown model type: {model_type}. Available for {task}: {list(registry.keys())}")
        wrapper_cls = registry[model_type]
        params = parameters or {}
        params.setdefault("random_state", random_seed)
        self._model: BaseModelWrapper = wrapper_cls(**params)
        self._model_type = model_type
        self._random_seed = random_seed
        self._task = task
        self._experiment = ExperimentTracker()

    def _evaluate(self, y_true, preds, proba) -> dict[str, Any]:
        if self._task == "regression":
            return evaluate_regression(y_true, preds)
        return evaluate_classification(y_true, preds, proba)

    async def train(self, model_name: str, X_train: pd.DataFrame, y_train: pd.Series,
                    X_val: pd.DataFrame | None = None, y_val: pd.Series | None = None,
                    dataset_version: int | None = None,
                    feature_version: int | None = None) -> dict[str, Any]:
        start_time = time.time()
        from backend.shared.config import GIT_COMMIT as git_commit

        self._experiment.start_run(
            model_name=model_name,
            dataset_version=dataset_version,
            feature_version=feature_version,
            git_commit=git_commit,
        )
        self._experiment.log_params(self._model.get_params())
        eval_set = [(X_val, y_val)] if X_val is not None and y_val is not None else None
        self._model.fit(X_train, y_train, eval_set=eval_set)

        elapsed = time.time() - start_time

        train_preds = self._model.predict(X_train)
        train_proba = self._model.predict_proba(X_train) if self._task == "classification" else None
        train_metrics = self._evaluate(y_train, train_preds, train_proba)
        self._experiment.log_metrics(_scalar_metrics({f"train_{k}": v for k, v in train_metrics.items()}))

        val_metrics = {}
        if X_val is not None and y_val is not None:
            val_preds = self._model.predict(X_val)
            val_proba = self._model.predict_proba(X_val) if self._task == "classification" else None
            val_metrics = self._evaluate(y_val, val_preds, val_proba)
            self._experiment.log_metrics(_scalar_metrics({f"val_{k}": v for k, v in val_metrics.items()}))

        artifact_dir = Path(ARTIFACT_DIR) / model_name / f"v{dataset_version or 0}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = str(artifact_dir / "model.joblib")
        self._model.save(artifact_path)
        self._experiment.log_artifact(artifact_path)

        all_metrics = {**{f"train_{k}": v for k, v in train_metrics.items()},
                       **{f"val_{k}": v for k, v in val_metrics.items()}}

        pool = await get_pool()
        existing_version = await pool.fetchval(
            "SELECT MAX(version) FROM ml.model_versions WHERE name = $1", model_name
        )
        version = (existing_version or 0) + 1

        row = await pool.fetchrow(
            "INSERT INTO ml.model_versions "
            "(name, version, model_type, stage, metrics, parameters, dataset_version, feature_version, "
            "mlflow_run_id, artifact_path, file_path, git_commit_hash, execution_time_seconds) "
            "VALUES ($1, $2, $3, 'development', $4, $5, $6, $7, $8, $9, $10, $11, $12) "
            "RETURNING uuid, name, version, stage, mlflow_run_id, execution_time_seconds",
            model_name, version, self._model_type,
            {k: float(v) if isinstance(v, (int, float)) else v for k, v in all_metrics.items()},
            self._model.get_params(),
            dataset_version, feature_version,
            self._experiment.run_id, artifact_path, artifact_path,
            git_commit, elapsed,
        )

        self._experiment.end_run()
        logger.info("training complete", model=model_name, version=version, metrics=all_metrics)

        return {
            "model_version_uuid": row["uuid"],
            "model_name": row["name"],
            "model_version": row["version"],
            "stage": row["stage"],
            "metrics": all_metrics,
            "mlflow_run_id": row["mlflow_run_id"],
            "execution_time_seconds": row["execution_time_seconds"],
        }
