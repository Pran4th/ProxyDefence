import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
    calinski_harabasz_score, davies_bouldin_score, silhouette_score,
)

from backend.shared.config import GIT_COMMIT
from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR
from db import get_pool

from .base import BaseTrainer


class ClusteringTrainer(BaseTrainer):
    async def prepare(self, X_train: Any, y_train: Any,
                      X_val: Any = None, y_val: Any = None,
                      X_test: Any = None, y_test: Any = None) -> None:
        self._X_train = X_train
        self._y_train = None
        self._X_val = X_val
        self._y_val = None
        self._X_test = X_test
        self._y_test = y_test
        self._logger.info("clustering data prepared (unsupervised, labels not required)")

    async def train(self) -> dict[str, float]:
        start = time.time()
        self._model.fit(self._X_train)
        elapsed = time.time() - start
        self._is_fitted = True
        self._training_time = elapsed
        labels = self._model.labels_ if hasattr(self._model, "labels_") else self._model.predict(self._X_train)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = int(np.sum(labels == -1)) if -1 in labels else 0
        inertia = float(self._model.inertia_) if hasattr(self._model, "inertia_") else 0.0
        self._train_metrics = {
            "training_time": round(elapsed, 4),
            "n_clusters": n_clusters,
            "n_noise": n_noise,
            "inertia": inertia,
        }
        self._logger.info("clustering complete in %.2fs, %d clusters", elapsed, n_clusters)
        return self._train_metrics

    async def predict(self, X: Any) -> Any:
        return self._model.predict(X)

    async def evaluate(self, X: Any = None, y: Any = None) -> dict[str, float]:
        X = X if X is not None else self._X_test
        y = y if y is not None else self._y_test
        X_eval = X if X is not None else self._X_train
        if X_eval is None:
            return {}
        labels = self._model.labels_ if hasattr(self._model, "labels_") else self._model.predict(X_eval)
        metrics: dict[str, float] = {}
        n_unique_labels = len(set(labels)) - (1 if -1 in labels else 0)
        if n_unique_labels >= 2:
            try:
                metrics["silhouette_score"] = float(silhouette_score(X_eval, labels))
            except Exception:
                pass
            try:
                metrics["davies_bouldin_score"] = float(davies_bouldin_score(X_eval, labels))
            except Exception:
                pass
            try:
                metrics["calinski_harabasz_score"] = float(calinski_harabasz_score(X_eval, labels))
            except Exception:
                pass
        if hasattr(self._model, "inertia_"):
            metrics["inertia"] = float(self._model.inertia_)
        if len(np.unique(labels)) >= 2:
            from scipy.spatial.distance import cdist
            centroids = np.array([X_eval[labels == c].mean(axis=0) for c in np.unique(labels) if c != -1])
            if len(centroids) >= 2:
                inter_cluster_dist = np.min(cdist(centroids, centroids) + np.eye(len(centroids)) * 1e10)
                metrics["min_inter_cluster_distance"] = float(inter_cluster_dist)
        n_noise = int(np.sum(labels == -1)) if -1 in labels else 0
        metrics["n_clusters"] = float(n_unique_labels)
        metrics["n_noise"] = float(n_noise)
        return metrics

    async def save(self, path: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._model, str(p))
        self._logger.info("model saved to %s", path)
        return str(p)

    async def load(self, path: str) -> None:
        self._model = joblib.load(path)
        self._is_fitted = True
        self._logger.info("model loaded from %s", path)

    async def export(self, format: str = "joblib") -> str:
        export_path = self._config.get("export_path", str(Path(ARTIFACT_DIR) / "exports"))
        p = Path(export_path)
        p.mkdir(parents=True, exist_ok=True)
        model_type = self._config.get("model_type", "model")
        if format == "joblib":
            path = str(p / f"{model_type}.joblib")
            joblib.dump(self._model, path)
        elif format == "pkl":
            import pickle
            path = str(p / f"{model_type}.pkl")
            with open(path, "wb") as f:
                pickle.dump(self._model, f)
        elif format == "onnx":
            path = str(p / f"{model_type}.onnx")
            try:
                from skl2onnx import convert_sklearn
                from skl2onnx.common.data_types import FloatTensorType
                n_features = self._X_train.shape[1] if hasattr(self._X_train, "shape") else 10
                initial_type = [("float_input", FloatTensorType([None, n_features]))]
                onx = convert_sklearn(self._model, initial_types=initial_type)
                with open(path, "wb") as f:
                    f.write(onx.SerializeToString())
            except ImportError:
                self._logger.warning("skl2onnx not available, falling back to joblib")
                path = str(p / f"{model_type}.joblib")
                joblib.dump(self._model, path)
        else:
            path = str(p / f"{model_type}.joblib")
            joblib.dump(self._model, path)
        self._logger.info("model exported to %s", path)
        return path

    async def register(self, experiment_name: str, run_id: str,
                       metrics: dict, tags: dict = None,
                       pool: Any = None) -> str:
        db_pool = pool or await get_pool()
        model_name = self._config.get("model_name", experiment_name)
        existing_version = await db_pool.fetchval(
            "SELECT MAX(version) FROM ml.model_versions WHERE name = $1", model_name,
        )
        version = (existing_version or 0) + 1
        model_type_str = self._config.get("model_type", type(self._model).__name__)
        params = self.get_params()
        row = await db_pool.fetchrow(
            "INSERT INTO ml.model_versions "
            "(name, version, model_type, stage, metrics, parameters, feature_version, "
            "dataset_version, experiment_id, mlflow_run_id, artifact_path, file_path, "
            "git_commit_hash, execution_time_seconds) "
            "VALUES ($1, $2, $3, 'development', $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) "
            "RETURNING uuid",
            model_name, version, model_type_str,
            json.dumps({k: float(v) if isinstance(v, (int, float)) else v for k, v in metrics.items()}),
            json.dumps(params),
            self._config.get("feature_version"),
            self._config.get("dataset_version"),
            experiment_name, run_id,
            self._config.get("artifact_path", ""),
            self._config.get("file_path", ""),
            GIT_COMMIT, self._training_time,
        )
        model_version_uuid = row["uuid"]
        if tags:
            await db_pool.execute(
                "INSERT INTO ml.model_governance "
                "(model_version_uuid, action, actor, reason, metadata) "
                "VALUES ($1, 'registered', 'system', 'registered via research trainer', $2)",
                model_version_uuid, json.dumps(tags),
            )
        self._logger.info("model registered as %s v%d (%s)", model_name, version, model_version_uuid)
        return model_version_uuid
