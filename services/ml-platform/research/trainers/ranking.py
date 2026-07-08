import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from backend.shared.config import GIT_COMMIT
from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR
from db import get_pool

from .base import BaseTrainer


class RankingTrainer(BaseTrainer):
    def __init__(self, model: Any, config: dict, logger: Any = None):
        super().__init__(model, config, logger)
        self._query_groups: Any = None
        self._group_indices: list[list[int]] = []

    async def prepare(self, X_train: Any, y_train: Any,
                      X_val: Any = None, y_val: Any = None,
                      X_test: Any = None, y_test: Any = None) -> None:
        self._X_train = X_train
        self._y_train = y_train
        self._X_val = X_val
        self._y_val = y_val
        self._X_test = X_test
        self._y_test = y_test
        query_config = self._config.get("query_groups", {})
        group_col = query_config.get("group_column")
        if group_col is not None and hasattr(X_train, "__getitem__"):
            if hasattr(X_train, "iloc"):
                self._query_groups = X_train.iloc[:, group_col] if isinstance(group_col, int) else X_train[group_col]
            elif hasattr(X_train, "__getitem__"):
                self._query_groups = X_train[:, group_col] if isinstance(group_col, int) else X_train[group_col]
        if self._query_groups is not None:
            unique_groups = np.unique(self._query_groups)
            self._group_indices = [np.where(self._query_groups == g)[0].tolist() for g in unique_groups]
            self._logger.info("built %d query groups for ranking", len(self._group_indices))
        else:
            self._group_indices = [list(range(len(X_train)))]
        self._logger.info("ranking data prepared with %d groups", len(self._group_indices))

    async def train(self) -> dict[str, float]:
        start = time.time()
        if hasattr(self._model, "fit") and "group" in self._model.fit.__code__.co_varnames:
            group_sizes = [len(g) for g in self._group_indices]
            eval_set = None
            if self._X_val is not None and self._y_val is not None:
                eval_set = [(self._X_val, self._y_val)]
            self._model.fit(self._X_train, self._y_train, group=group_sizes, eval_set=eval_set)
        elif hasattr(self._model, "fit") and "qid" in self._model.fit.__code__.co_varnames:
            self._model.fit(self._X_train, self._y_train, qid=self._query_groups)
        else:
            self._model.fit(self._X_train, self._y_train)
        elapsed = time.time() - start
        self._is_fitted = True
        self._training_time = elapsed
        self._train_metrics = {"training_time": round(elapsed, 4), "n_groups": len(self._group_indices)}
        self._logger.info("ranking training complete in %.2fs", elapsed)
        return self._train_metrics

    async def predict(self, X: Any) -> Any:
        scores = self._model.predict(X)
        return scores

    async def evaluate(self, X: Any = None, y: Any = None) -> dict[str, float]:
        X = X if X is not None else self._X_test
        y = y if y is not None else self._y_test
        if X is None or y is None:
            return {}
        scores = self._model.predict(X)
        y_arr = np.asarray(y)
        metrics: dict[str, float] = {}
        default_k = self._config.get("ndcg_at_k", [1, 5, 10])
        group_data = []
        if self._query_groups is not None and X is not self._X_train:
            group_col = self._config.get("query_groups", {}).get("group_column")
            if group_col is not None and hasattr(X, "iloc"):
                eval_groups = X.iloc[:, group_col] if isinstance(group_col, int) else X[group_col]
                unique_groups = np.unique(eval_groups)
                group_data = [np.where(eval_groups == g)[0].tolist() for g in unique_groups]
            else:
                group_data = [list(range(len(X)))]
        else:
            group_data = [list(range(len(X)))]
        for k in default_k:
            ndcg_scores = []
            for group_idx in group_data:
                if len(group_idx) < 2:
                    continue
                g_scores = scores[group_idx]
                g_relevance = y_arr[group_idx]
                if np.sum(g_relevance) == 0:
                    continue
                sorted_by_score = np.argsort(g_scores)[::-1][:k]
                ideal = np.argsort(g_relevance)[::-1][:k]
                dcg = float(np.sum((2 ** g_relevance[sorted_by_score] - 1) / np.log2(np.arange(2, len(sorted_by_score) + 2))))
                idcg = float(np.sum((2 ** g_relevance[ideal] - 1) / np.log2(np.arange(2, len(ideal) + 2))))
                ndcg_scores.append(dcg / idcg if idcg > 0 else 0.0)
            if ndcg_scores:
                metrics[f"ndcg@{k}"] = float(np.mean(ndcg_scores))
        for k in default_k:
            ap_scores = []
            for group_idx in group_data:
                if len(group_idx) < 2:
                    continue
                g_scores = scores[group_idx]
                g_relevance = y_arr[group_idx]
                if np.sum(g_relevance) == 0:
                    continue
                sorted_by_score = np.argsort(g_scores)[::-1][:k]
                relevant_at_k = g_relevance[sorted_by_score]
                precisions = []
                n_relevant = 0
                for i, rel in enumerate(relevant_at_k):
                    if rel > 0:
                        n_relevant += 1
                        precisions.append(n_relevant / (i + 1))
                ap_scores.append(float(np.mean(precisions)) if precisions else 0.0)
            if ap_scores:
                metrics[f"map@{k}"] = float(np.mean(ap_scores))
        for k in default_k:
            mrr_scores = []
            for group_idx in group_data:
                if len(group_idx) < 2:
                    continue
                g_scores = scores[group_idx]
                g_relevance = y_arr[group_idx]
                sorted_by_score = np.argsort(g_scores)[::-1][:k]
                for rank, idx in enumerate(sorted_by_score):
                    if g_relevance[idx] > 0:
                        mrr_scores.append(1.0 / (rank + 1))
                        break
                else:
                    mrr_scores.append(0.0)
            if mrr_scores:
                metrics[f"mrr@{k}"] = float(np.mean(mrr_scores))
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
