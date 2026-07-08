import numpy as np
import pytest

from evaluation.classification import evaluate_classification
from evaluation.regression import evaluate_regression
from evaluation.reporter import EvaluationReporter


class TestClassification:
    def test_perfect_prediction(self):
        y_true = np.array([0, 1, 2, 3])
        y_pred = np.array([0, 1, 2, 3])
        y_proba = np.eye(4)
        metrics = evaluate_classification(y_true, y_pred, y_proba)
        assert metrics["accuracy"] == 1.0
        assert metrics["f1_weighted"] == 1.0

    def test_all_wrong(self):
        y_true = np.array([0, 0, 0, 1])
        y_pred = np.array([1, 1, 1, 0])
        metrics = evaluate_classification(y_true, y_pred)
        assert metrics["accuracy"] < 0.5

    def test_confusion_matrix_shape(self):
        y_true = np.array([0, 1, 2])
        y_pred = np.array([0, 1, 2])
        metrics = evaluate_classification(y_true, y_pred)
        cm = np.array(metrics["confusion_matrix"])
        assert cm.shape == (3, 3)

    def test_classification_report(self):
        y_true = np.array([0, 0, 1, 1, 2, 2])
        y_pred = np.array([0, 0, 1, 1, 2, 2])
        metrics = evaluate_classification(y_true, y_pred)
        report = metrics["classification_report"]
        assert "0" in report
        assert report["accuracy"] == 1.0


class TestRegression:
    def test_perfect_prediction(self):
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.0, 2.0, 3.0])
        metrics = evaluate_regression(y_true, y_pred)
        assert metrics["mae"] == 0.0
        assert metrics["rmse"] == 0.0
        assert metrics["r2"] == 1.0

    def test_mae_value(self):
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([2.0, 3.0, 4.0])
        metrics = evaluate_regression(y_true, y_pred)
        assert metrics["mae"] == 1.0
        assert metrics["r2"] < 0


class TestEvaluationReporter:
    def test_generate_report_structure(self):
        reporter = EvaluationReporter()
        report = reporter.generate_report(
            metrics={"accuracy": 0.95, "f1": 0.94},
            model_name="test_model",
            model_version=1,
            dataset_version=1,
            cv_scores=[0.93, 0.94, 0.95],
        )
        assert report["model_name"] == "test_model"
        assert report["model_version"] == 1
        assert report["dataset_version"] == 1
        assert "cross_validation" in report
        assert report["cross_validation"]["mean"] == pytest.approx(0.94, abs=0.01)

    def test_markdown_format(self):
        reporter = EvaluationReporter()
        report = reporter.generate_report(
            metrics={"accuracy": 0.95},
            model_name="test_model",
            model_version=1,
        )
        md = reporter.format_markdown(report)
        assert "test_model" in md
        assert "0.9500" in md
