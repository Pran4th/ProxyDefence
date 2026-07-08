import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score,
)

from config import ARTIFACT_DIR
from backend.shared.config import GIT_COMMIT
from backend.shared.logging_config import get_logger
from db import get_pool

from .base import BaseTrainer


class ClassificationTrainer(BaseTrainer):
    def __init__(self, model: Any, config: dict, logger: Any = None):
        super().__init__(model, config, logger)
        self._n_classes: int | None = None
        self._class_names: list | None = None

    async def prepare(self, X_train: Any, y_train: Any,
                      X_val: Any = None, y_val: Any = None,
                      X_test: Any = None, y_test: Any = None) -> None:
        self._X_train = X_train
        self._y_train = y_train
        self._X_val = X_val
        self._y_val = y_val
        self._X_test = X_test
        self._y_test = y_test
        if y_train is not None:
            self._n_classes = len(np.unique(y_train))
            self._class_names = list(np.unique(y_train))
        imbalance_config = self._config.get("class_imbalance", {})
        if imbalance_config.get("enabled", False) and hasattr(self._model, "set_params"):
            method = imbalance_config.get("method", "balanced")
            if method == "balanced":
                self._model.set_params(class_weight="balanced")
            elif method == "sample_weight" and imbalance_config.get("scale_pos_weight"):
                self._logger.info("class imbalance config applied: %s", method)
        self._logger.info("data prepared with %d classes", self._n_classes)

    async def train(self) -> dict[str, float]:
        start = time.time()
        eval_set = self._config.get("eval_set")
        if eval_set and self._X_val is not None and self._y_val is not None:
            if hasattr(self._model, "fit") and "eval_set" in self._model.fit.__code__.co_varnames:
                fit_args = {"eval_set": [(self._X_val, self._y_val)]}
                if hasattr(self._model, "early_stopping_rounds"):
                    fit_args["early_stopping_rounds"] = self._config.get("early_stopping_rounds", 10)
                if hasattr(self._model, "verbose"):
                    fit_args["verbose"] = self._config.get("verbose", False)
                self._model.fit(self._X_train, self._y_train, **fit_args)
            else:
                self._model.fit(self._X_train, self._y_train)
        else:
            self._model.fit(self._X_train, self._y_train)
        elapsed = time.time() - start
        self._is_fitted = True
        self._training_time = elapsed
        train_preds = self._model.predict(self._X_train)
        train_acc = float(accuracy_score(self._y_train, train_preds))
        self._train_metrics = {"training_time": round(elapsed, 4), "train_accuracy": train_acc}
        self._logger.info("training complete in %.2fs, train_acc=%.4f", elapsed, train_acc)
        return self._train_metrics

    async def predict(self, X: Any) -> Any:
        if hasattr(self._model, "predict_proba"):
            return self._model.predict_proba(X)
        return self._model.predict(X)

    async def evaluate(self, X: Any = None, y: Any = None) -> dict[str, float]:
        X = X if X is not None else self._X_test
        y = y if y is not None else self._y_test
        if X is None or y is None:
            return {}
        preds = self._model.predict(X)
        metrics: dict[str, float] = {
            "accuracy": float(accuracy_score(y, preds)),
            "precision": float(precision_score(y, preds, average="weighted", zero_division=0)),
            "recall": float(recall_score(y, preds, average="weighted", zero_division=0)),
            "f1": float(f1_score(y, preds, average="weighted", zero_division=0)),
        }
        if hasattr(self._model, "predict_proba"):
            try:
                proba = self._model.predict_proba(X)
                if proba.shape[1] == 2:
                    metrics["roc_auc"] = float(roc_auc_score(y, proba[:, 1]))
                elif self._n_classes and self._n_classes > 2:
                    metrics["roc_auc_ovr"] = float(roc_auc_score(y, proba, multi_class="ovr"))
            except Exception:
                pass
        cm = confusion_matrix(y, preds).tolist()
        metrics["confusion_matrix"] = json.dumps(cm)
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
