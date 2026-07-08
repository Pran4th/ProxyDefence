from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pytest

from research.evaluation.anomaly import compute_anomaly_metrics, compute_precision_at_k
from research.evaluation.classification import (
    compute_classification_metrics, compute_confusion_matrix, compute_pr_curve, compute_roc_curve,
)
from research.evaluation.engine import EvaluationEngine
from research.evaluation.forecasting import (
    compute_forecasting_metrics, compute_mase, compute_rolling_window_error, compute_smape,
)
from research.evaluation.regression import (
    compute_mape, compute_regression_metrics, compute_residual_analysis,
)
from research.evaluation.regression import test_normality as _test_normality_func
from research.evaluation.results import (
    ConfusionMatrix, EvaluationResult, MetricValue, ProblemType, ROCCurve, ResidualAnalysis,
)


class TestProblemType:
    def test_enum_values(self):
        assert ProblemType.CLASSIFICATION.value == "classification"
        assert ProblemType.REGRESSION.value == "regression"
        assert ProblemType.FORECASTING.value == "forecasting"
        assert ProblemType.ANOMALY_DETECTION.value == "anomaly_detection"
        assert ProblemType.CLUSTERING.value == "clustering"
        assert ProblemType.RANKING.value == "ranking"

    def test_enum_members(self):
        assert len(ProblemType) == 6


class TestMetricValue:
    def test_dataclass(self):
        mv = MetricValue(name="accuracy", value=0.95)
        assert mv.std is None
        assert mv.ci_lower is None

    def test_with_stats(self):
        mv = MetricValue(name="f1", value=0.9, std=0.05, ci_lower=0.85, ci_upper=0.95)
        assert mv.std == 0.05


class TestEvaluationResult:
    def test_dataclass(self):
        er = EvaluationResult(
            problem_type=ProblemType.CLASSIFICATION,
            model_name="model_a",
            metrics={"accuracy": 0.95},
        )
        assert er.metric_details == {}
        assert er.n_samples == 0


class TestConfusionMatrix:
    def test_dataclass(self):
        cm = ConfusionMatrix(
            matrix=[[5, 1], [2, 4]], labels=["pos", "neg"],
            tp=5, fp=1, fn=2, tn=4,
        )
        assert cm.tp == 5
        assert cm.normalized is False


class TestROCCurve:
    def test_dataclass(self):
        roc = ROCCurve(
            fpr=[0.0, 0.5, 1.0], tpr=[0.0, 0.8, 1.0],
            thresholds=[2.0, 1.0, 0.0], auc=0.9,
        )
        assert roc.auc == 0.9


class TestResidualAnalysis:
    def test_dataclass(self):
        ra = ResidualAnalysis(
            residuals=[1.0, -0.5, 0.3], mean=0.267, std=0.65,
            skewness=0.1, normality_pvalue=0.5, heteroscedasticity=False,
        )
        assert abs(ra.mean - 0.267) < 0.01


class TestEvaluationEngine:
    @pytest.mark.asyncio
    async def test_detect_problem_type_float(self):
        engine = EvaluationEngine()
        pt = await engine.detect_problem_type(np.array([1.0, 2.5, 3.2]))
        assert pt == ProblemType.REGRESSION

    @pytest.mark.asyncio
    async def test_detect_problem_type_classification(self):
        engine = EvaluationEngine()
        pt = await engine.detect_problem_type(np.array([0, 1, 2, 1, 0]))
        assert pt == ProblemType.CLASSIFICATION

    @pytest.mark.asyncio
    async def test_detect_problem_type_forecasting(self):
        engine = EvaluationEngine()
        pt = await engine.detect_problem_type(np.array([1, 2, 3, 4, 5]))
        assert pt == ProblemType.FORECASTING

    @pytest.mark.asyncio
    async def test_detect_problem_type_large_integer(self):
        engine = EvaluationEngine()
        y = np.random.randint(0, 100, 50)
        pt = await engine.detect_problem_type(y)
        assert pt in (ProblemType.FORECASTING, ProblemType.REGRESSION)

    @pytest.mark.asyncio
    async def test_evaluate_classification(self):
        engine = EvaluationEngine()
        y_true = np.array([0, 1, 0, 1, 0])
        y_pred = np.array([0, 1, 0, 1, 0])
        result = await engine.evaluate(y_true, y_pred, problem_type=ProblemType.CLASSIFICATION)
        assert result.problem_type == ProblemType.CLASSIFICATION
        assert result.metrics["accuracy"] == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_classification_with_proba(self):
        engine = EvaluationEngine()
        y_true = np.array([0, 1, 0, 1, 0])
        y_pred = np.array([0, 1, 0, 1, 0])
        y_proba = np.array([[0.9, 0.1], [0.2, 0.8], [0.8, 0.2], [0.3, 0.7], [0.9, 0.1]])
        result = await engine.evaluate(y_true, y_pred, y_proba=y_proba, problem_type="classification")
        assert result.metrics["accuracy"] == 1.0
        assert "confusion_matrix" in result.metric_details

    @pytest.mark.asyncio
    async def test_evaluate_regression(self):
        engine = EvaluationEngine()
        y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = await engine.evaluate(y_true, y_pred, problem_type=ProblemType.REGRESSION)
        assert result.problem_type == ProblemType.REGRESSION
        assert result.metrics["r2"] == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_forecasting(self):
        engine = EvaluationEngine()
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0])
        result = await engine.evaluate(y_true, y_pred, problem_type=ProblemType.FORECASTING)
        assert result.problem_type == ProblemType.FORECASTING

    @pytest.mark.asyncio
    async def test_evaluate_anomaly(self):
        engine = EvaluationEngine()
        y_true = np.array([0, 1, 0, 1, 0])
        y_pred = np.array([0, 1, 0, 1, 0])
        result = await engine.evaluate(y_true, y_pred, problem_type=ProblemType.ANOMALY_DETECTION)
        assert result.problem_type == ProblemType.ANOMALY_DETECTION

    @pytest.mark.asyncio
    async def test_evaluate_auto_detect(self):
        engine = EvaluationEngine()
        result = await engine.evaluate(np.array([0, 1, 0]), np.array([0, 1, 0]))
        assert result.problem_type == ProblemType.CLASSIFICATION

    @pytest.mark.asyncio
    async def test_compare_models_empty(self):
        engine = EvaluationEngine()
        result = await engine.compare_models({})
        assert result["models"] == []

    @pytest.mark.asyncio
    async def test_compare_models(self):
        engine = EvaluationEngine()
        r1 = EvaluationResult(ProblemType.CLASSIFICATION, "a", {"f1": 0.9})
        r2 = EvaluationResult(ProblemType.CLASSIFICATION, "b", {"f1": 0.8})
        result = await engine.compare_models({"a": r1, "b": r2})
        assert result["best_model"] == "a"

    def test_confusion_matrix_static(self):
        cm = EvaluationEngine.confusion_matrix(np.array([0, 1, 0]), np.array([0, 1, 1]))
        assert len(cm) == 2


class TestClassificationMetrics:
    def test_compute_confusion_matrix(self):
        y_true = np.array([0, 1, 0, 1, 0])
        y_pred = np.array([0, 1, 0, 1, 0])
        cm = compute_confusion_matrix(y_true, y_pred)
        assert isinstance(cm, ConfusionMatrix)
        assert cm.matrix is not None
        assert cm.labels is not None

    def test_compute_confusion_matrix_with_errors(self):
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 0, 1, 1])
        cm = compute_confusion_matrix(y_true, y_pred)
        assert isinstance(cm, ConfusionMatrix)
        assert cm.matrix is not None

    def test_compute_roc_curve(self):
        y_true = np.array([0, 0, 1, 1])
        y_score = np.array([0.1, 0.2, 0.8, 0.9])
        roc = compute_roc_curve(y_true, y_score)
        assert roc.auc >= 0
        assert len(roc.fpr) == len(roc.tpr)

    def test_compute_classification_metrics_binary(self):
        y_true = np.array([0, 0, 1, 1, 0])
        y_pred = np.array([0, 0, 1, 1, 1])
        metrics = compute_classification_metrics(y_true, y_pred)
        assert metrics["accuracy"] >= 0
        assert "f1_weighted" in metrics
        assert "roc_auc" not in metrics

    def test_compute_classification_metrics_binary_with_proba(self):
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 1])
        y_proba = np.array([[0.9, 0.1], [0.8, 0.2], [0.3, 0.7], [0.2, 0.8]])
        metrics = compute_classification_metrics(y_true, y_pred, y_proba)
        assert metrics["roc_auc"] is not None

    def test_compute_classification_metrics_multi_class(self):
        y_true = np.array([0, 1, 2, 0, 1])
        y_pred = np.array([0, 1, 2, 0, 1])
        metrics = compute_classification_metrics(y_true, y_pred)
        assert "f1_macro" in metrics

    def test_compute_pr_curve(self):
        y_true = np.array([0, 0, 1, 1])
        y_score = np.array([0.1, 0.2, 0.8, 0.9])
        result = compute_pr_curve(y_true, y_score)
        assert "pr_auc" in result
        assert "precision" in result


class TestRegressionMetrics:
    def test_compute_regression_metrics(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0])
        metrics = compute_regression_metrics(y_true, y_pred)
        assert metrics["mse"] == 0.0
        assert metrics["r2"] == 1.0

    def test_compute_regression_metrics_with_error(self):
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.5, 2.5, 3.5])
        metrics = compute_regression_metrics(y_true, y_pred)
        assert metrics["mae"] > 0.0
        assert "mape" in metrics

    def test_compute_mape(self):
        y_true = np.array([100.0, 200.0, 300.0])
        y_pred = np.array([110.0, 190.0, 290.0])
        mape = compute_mape(y_true, y_pred)
        assert mape > 0.0

    def test_compute_mape_all_zero(self):
        y_true = np.array([0.0, 0.0])
        y_pred = np.array([1.0, 2.0])
        assert compute_mape(y_true, y_pred) == float("inf")

    def test_compute_residual_analysis(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = np.array([1.1, 2.2, 3.0, 3.9, 5.1])
        ra = compute_residual_analysis(y_true, y_pred)
        assert isinstance(ra, ResidualAnalysis)
        assert ra.mean is not None
        assert ra.std is not None

    def test_test_normality_few_samples(self):
        assert _test_normality_func(np.array([1.0, 2.0, 3.0])) == 1.0

    def test_test_normality_many_samples(self):
        p = _test_normality_func(np.random.randn(50))
        assert 0 <= p <= 1


class TestForecastingMetrics:
    def test_compute_smape(self):
        y_true = np.array([100.0, 200.0, 300.0])
        y_pred = np.array([110.0, 190.0, 290.0])
        smape = compute_smape(y_true, y_pred)
        assert smape > 0.0

    def test_compute_smape_all_zero_denom(self):
        y_true = np.array([0.0, 0.0])
        y_pred = np.array([0.0, 0.0])
        assert compute_smape(y_true, y_pred) == 0.0

    def test_compute_mase_no_train(self):
        y_true = np.array([1.0, 2.0])
        y_pred = np.array([1.0, 2.0])
        result = compute_mase(y_true, y_pred)
        assert np.isnan(result)

    def test_compute_mase_with_train(self):
        y_true = np.array([4.0, 5.0])
        y_pred = np.array([4.1, 5.1])
        y_train = np.array([1.0, 2.0, 3.0])
        mase = compute_mase(y_true, y_pred, y_train, seasonal_period=1)
        assert not np.isnan(mase)

    def test_compute_mase_zero_denom(self):
        y_true = np.array([4.0, 5.0])
        y_pred = np.array([4.0, 5.0])
        y_train = np.array([1.0, 1.0, 1.0])
        mase = compute_mase(y_true, y_pred, y_train, seasonal_period=1)
        assert np.isnan(mase)

    def test_rolling_window_error(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        err = compute_rolling_window_error(y_true, y_pred, window=3)
        assert err == 0.0

    def test_rolling_window_error_too_small(self):
        err = compute_rolling_window_error(np.array([1.0]), np.array([1.0]), window=5)
        assert err == 0.0

    def test_compute_forecasting_metrics(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0])
        metrics = compute_forecasting_metrics(y_true, y_pred)
        assert "smape" in metrics
        assert "rmse" in metrics

    def test_compute_forecasting_metrics_with_seasonal(self):
        y_true = np.array([4.0, 5.0, 6.0])
        y_pred = np.array([4.0, 5.0, 6.0])
        y_train = np.array([1.0, 2.0, 3.0])
        metrics = compute_forecasting_metrics(y_true, y_pred, y_train, seasonal_period=1)
        assert "mase" in metrics


class TestAnomalyMetrics:
    def test_compute_precision_at_k(self):
        y_true = np.array([0, 1, 0, 1, 0])
        y_score = np.array([0.1, 0.9, 0.2, 0.8, 0.3])
        p_at_k = compute_precision_at_k(y_true, y_score, k=3)
        assert 0 <= p_at_k <= 1

    def test_compute_precision_at_k_zero(self):
        assert compute_precision_at_k(np.array([]), np.array([]), 0) == 0.0

    def test_compute_anomaly_metrics(self):
        y_true = np.array([0, 1, 0, 1, 0])
        y_pred = np.array([0, 1, 0, 1, 0])
        metrics = compute_anomaly_metrics(y_true, y_pred)
        assert metrics["f1"] == 1.0
        assert "confusion_matrix" in metrics
