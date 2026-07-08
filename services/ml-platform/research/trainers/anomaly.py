import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
    auc, confusion_matrix, precision_recall_curve, roc_auc_score,
)

from backend.shared.config import GIT_COMMIT
from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR
from db import get_pool

from .base import BaseTrainer


class AnomalyTrainer(BaseTrainer):
    def __init__(self, model: Any, config: dict, logger: Any = None):
        super().__init__(model, config, logger)
        self._contamination: float = config.get("contamination", 0.1)
        self._threshold_strategy: str = config.get("threshold_strategy", "auto")
        self._threshold: float = config.get("threshold", 0.5)

    async def prepare(self, X_train: Any, y_train: Any,
                      X_val: Any = None, y_val: Any = None,
                      X_test: Any = None, y_test: Any = None) -> None:
        self._X_train = X_train
        self._y_train = y_train
        self._X_val = X_val
        self._y_val = y_val
        self._X_test = X_test
        self._y_test = y_test
        if hasattr(self._model, "set_params") and "contamination" in self._model.get_params():
            self._model.set_params(contamination=self._contamination)
        self._logger.info(
            "anomaly data prepared, contamination=%.3f, threshold_strategy=%s",
            self._contamination, self._threshold_strategy,
        )

    async def train(self) -> dict[str, float]:
        start = time.time()
        self._model.fit(self._X_train)
        elapsed = time.time() - start
        self._is_fitted = True
        self._training_time = elapsed
        train_scores = self._decision_function(self._X_train)
        n_anomalies = int(np.sum(train_scores > self._threshold)) if self._threshold_strategy == "fixed" else 0
        self._train_metrics = {
            "training_time": round(elapsed, 4),
            "n_samples": len(self._X_train) if hasattr(self._X_train, "__len__") else 0,
            "n_anomalies_detected": n_anomalies,
            "contamination": self._contamination,
        }
        self._logger.info("anomaly training complete in %.2fs", elapsed)
        return self._train_metrics

    def _decision_function(self, X: Any) -> np.ndarray:
        if hasattr(self._model, "decision_function"):
            scores = self._model.decision_function(X)
            return -scores if np.mean(scores) < 0 else scores
        if hasattr(self._model, "score_samples"):
            return -self._model.score_samples(X)
        if hasattr(self._model, "predict"):
            return self._model.predict(X).astype(float)
        return np.zeros(len(X))

    def _predict_labels(self, X: Any) -> np.ndarray:
        if hasattr(self._model, "predict"):
            return self._model.predict(X)
        scores = self._decision_function(X)
        if self._threshold_strategy == "auto":
            k = int(len(scores) * self._contamination)
            threshold = np.sort(scores)[-k] if k > 0 else scores.max()
        else:
            threshold = self._threshold
        return (scores > threshold).astype(int)

    async def predict(self, X: Any) -> Any:
        scores = self._decision_function(X)
        labels = self._predict_labels(X)
        return {"scores": scores, "labels": labels}

    async def evaluate(self, X: Any = None, y: Any = None) -> dict[str, float]:
        X = X if X is not None else self._X_test
        y = y if y is not None else self._y_test
        if X is None or y is None:
            return {}
        scores = self._decision_function(X)
        labels = self._predict_labels(X)
        y_arr = np.asarray(y)
        metrics: dict[str, float] = {}
        cm = confusion_matrix(y_arr, labels).tolist()
        metrics["confusion_matrix"] = json.dumps(cm)
        precision_k_vals = self._config.get("precision_at_k", [5, 10, 50, 100])
        sorted_idx = np.argsort(scores)[::-1]
        for k in precision_k_vals:
            k = min(k, len(sorted_idx))
            top_k = sorted_idx[:k]
            precision_k = float(np.mean(y_arr[top_k])) if k > 0 else 0.0
            metrics[f"precision@{k}"] = precision_k
        tp = float(np.sum((labels == 1) & (y_arr == 1)))
        fp = float(np.sum((labels == 1) & (y_arr == 0)))
        fn = float(np.sum((labels == 0) & (y_arr == 1)))
        recall_val = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision_val = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        metrics["precision"] = precision_val
        metrics["recall"] = recall_val
        metrics["f1"] = 2 * precision_val * recall_val / (precision_val + recall_val + 1e-10) if (precision_val + recall_val) > 0 else 0.0
        if len(np.unique(y_arr)) == 2:
            try:
                metrics["roc_auc"] = float(roc_auc_score(y_arr, scores))
            except Exception:
                pass
            try:
                prec_curve, rec_curve, _ = precision_recall_curve(y_arr, scores)
                metrics["auc_pr"] = float(auc(rec_curve, prec_curve))
            except Exception:
                pass
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
