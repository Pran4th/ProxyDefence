import time
from typing import Any

import numpy as np

from backend.shared.logging_config import get_logger
from research.evaluation.anomaly import compute_anomaly_metrics
from research.evaluation.classification import (
    compute_classification_metrics,
    compute_confusion_matrix,
    compute_roc_curve,
)
from research.evaluation.forecasting import compute_forecasting_metrics
from research.evaluation.regression import compute_regression_metrics, compute_residual_analysis
from research.evaluation.results import EvaluationResult, ProblemType

logger = get_logger(__name__)


class EvaluationEngine:
    async def evaluate(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray | None = None,
        problem_type: ProblemType | str | None = None,
        model: Any = None,
        X: np.ndarray | None = None,
        feature_names: list[str] | None = None,
    ) -> EvaluationResult:
        if problem_type is None:
            problem_type = await self.detect_problem_type(y_true)
        if isinstance(problem_type, str):
            problem_type = ProblemType(problem_type)

        n_samples = len(y_true)
        start = time.perf_counter()

        if problem_type == ProblemType.CLASSIFICATION:
            result = await self.evaluate_classification(y_true, y_pred, y_proba)
        elif problem_type == ProblemType.REGRESSION:
            result = await self.evaluate_regression(y_true, y_pred)
        elif problem_type == ProblemType.FORECASTING:
            result = await self.evaluate_forecasting(y_true, y_pred)
        elif problem_type == ProblemType.ANOMALY_DETECTION:
            result = await self.evaluate_anomaly(y_true, y_pred, y_proba)
        else:
            result = await self.evaluate_regression(y_true, y_pred)
            result.problem_type = problem_type

        result.duration_seconds = round(time.perf_counter() - start, 4)
        result.n_samples = n_samples
        result.feature_names = feature_names
        return result

    async def evaluate_classification(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray | None = None,
        labels: list[str] | None = None,
    ) -> EvaluationResult:
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        model_name = "classification_model"

        cm = compute_confusion_matrix(y_true, y_pred, labels)
        metrics = compute_classification_metrics(y_true, y_pred, y_proba, average="weighted")
        metrics_macro = compute_classification_metrics(y_true, y_pred, y_proba, average="macro")

        metric_details: dict[str, Any] = {
            "confusion_matrix": {
                "matrix": cm.matrix,
                "labels": cm.labels,
                "tp": cm.tp,
                "fp": cm.fp,
                "fn": cm.fn,
                "tn": cm.tn,
            },
        }

        unique = np.unique(y_true)
        if y_proba is not None and len(unique) == 2:
            roc = compute_roc_curve(y_true, y_proba[:, 1])
            metric_details["roc_curve"] = {
                "fpr": roc.fpr,
                "tpr": roc.tpr,
                "thresholds": roc.thresholds,
                "auc": roc.auc,
            }
        if y_proba is not None and len(unique) > 2:
            try:
                from sklearn.metrics import roc_auc_score
                roc_auc_val = round(float(roc_auc_score(y_true, y_proba, multi_class="ovr")), 6)
                metric_details["roc_auc_ovr"] = roc_auc_val
            except Exception:
                pass

        flat_metrics: dict[str, float | Any] = {}
        for k, v in metrics.items():
            flat_metrics[k] = v
        for k, v in metrics_macro.items():
            if k not in flat_metrics:
                flat_metrics[k] = v

        return EvaluationResult(
            problem_type=ProblemType.CLASSIFICATION,
            model_name=model_name,
            metrics=flat_metrics,
            metric_details=metric_details,
            n_samples=len(y_true),
        )

    async def evaluate_regression(self, y_true: np.ndarray, y_pred: np.ndarray) -> EvaluationResult:
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        model_name = "regression_model"

        metrics = compute_regression_metrics(y_true, y_pred)
        residual_analysis = compute_residual_analysis(y_true, y_pred)

        metric_details: dict[str, Any] = {
            "residual_analysis": {
                "mean": residual_analysis.mean,
                "std": residual_analysis.std,
                "skewness": residual_analysis.skewness,
                "normality_pvalue": residual_analysis.normality_pvalue,
                "heteroscedasticity": residual_analysis.heteroscedasticity,
            },
        }

        return EvaluationResult(
            problem_type=ProblemType.REGRESSION,
            model_name=model_name,
            metrics=metrics,
            metric_details=metric_details,
            n_samples=len(y_true),
        )

    async def evaluate_forecasting(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        seasonal_period: int | None = None,
    ) -> EvaluationResult:
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        model_name = "forecasting_model"
        y_train = None

        metrics = compute_forecasting_metrics(y_true, y_pred, y_train, seasonal_period)

        metric_details: dict[str, Any] = {
            "seasonal_period": seasonal_period,
            "residuals": (y_true - y_pred).flatten().tolist(),
        }

        return EvaluationResult(
            problem_type=ProblemType.FORECASTING,
            model_name=model_name,
            metrics=metrics,
            metric_details=metric_details,
            n_samples=len(y_true),
        )

    async def evaluate_anomaly(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_score: np.ndarray | None = None,
    ) -> EvaluationResult:
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        model_name = "anomaly_model"

        metrics = compute_anomaly_metrics(y_true, y_pred, y_score)
        cm = self.confusion_matrix(y_true, y_pred)

        metric_details: dict[str, Any] = {
            "confusion_matrix": cm,
        }
        if y_score is not None:
            try:
                from sklearn.metrics import roc_curve
                fpr, tpr, thresholds = roc_curve(y_true, y_score)
                metric_details["roc_curve"] = {
                    "fpr": fpr.tolist(),
                    "tpr": tpr.tolist(),
                    "thresholds": thresholds.tolist(),
                }
            except Exception:
                pass

        return EvaluationResult(
            problem_type=ProblemType.ANOMALY_DETECTION,
            model_name=model_name,
            metrics=metrics,
            metric_details=metric_details,
            n_samples=len(y_true),
        )

    async def detect_problem_type(self, y: np.ndarray) -> ProblemType:
        y = np.asarray(y)
        if np.issubdtype(y.dtype, np.floating) or y.dtype.kind == "f":
            return ProblemType.REGRESSION
        unique = np.unique(y)
        if np.issubdtype(y.dtype, np.integer) or y.dtype.kind in ("i", "u"):
            if len(unique) > 1:
                diffs = np.diff(y)
                if len(diffs) > 0 and np.all(diffs >= 0):
                    return ProblemType.FORECASTING
        if len(unique) <= 20:
            return ProblemType.CLASSIFICATION
        return ProblemType.REGRESSION

    async def compare_models(self, results: dict[str, EvaluationResult]) -> dict[str, Any]:
        if not results:
            return {"models": [], "best_model": None, "comparison": {}}

        comparison: dict[str, Any] = {
            "models": list(results.keys()),
            "problem_type": list(results.values())[0].problem_type.value,
            "metrics_comparison": {},
            "best_model": None,
        }

        all_metric_names: set[str] = set()
        for result in results.values():
            all_metric_names.update(result.metrics.keys())

        numeric_metrics = [
            m for m in all_metric_names
            if all(
                isinstance(result.metrics.get(m), (int, float))
                for result in results.values()
                if m in result.metrics
            )
        ]

        for metric_name in numeric_metrics:
            values = {}
            for model_name, result in results.items():
                if metric_name in result.metrics:
                    values[model_name] = result.metrics[metric_name]
            if values:
                comparison["metrics_comparison"][metric_name] = values

        metric_for_best = next(
            (m for m in ["f1_weighted", "roc_auc", "r2", "f1", "accuracy"] if m in numeric_metrics),
            numeric_metrics[0] if numeric_metrics else None,
        )
        if metric_for_best:
            best_model = max(results.items(), key=lambda x: x[1].metrics.get(metric_for_best, -float("inf")))
            comparison["best_model"] = best_model[0]
            comparison["best_metric"] = metric_for_best
            comparison["best_value"] = best_model[1].metrics[metric_for_best]

        return comparison

    @staticmethod
    def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> list[list[int]]:
        from sklearn.metrics import confusion_matrix as sk_cm
        return sk_cm(y_true, y_pred).tolist()
