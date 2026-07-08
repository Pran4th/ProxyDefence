from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProblemType(Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    FORECASTING = "forecasting"
    ANOMALY_DETECTION = "anomaly_detection"
    CLUSTERING = "clustering"
    RANKING = "ranking"


@dataclass
class MetricValue:
    name: str
    value: float
    std: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None


@dataclass
class EvaluationResult:
    problem_type: ProblemType
    model_name: str
    metrics: dict[str, float | MetricValue]
    metric_details: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    n_samples: int = 0
    feature_names: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfusionMatrix:
    matrix: list[list[int]]
    labels: list[str]
    normalized: bool = False
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0


@dataclass
class ROCCurve:
    fpr: list[float]
    tpr: list[float]
    thresholds: list[float]
    auc: float


@dataclass
class ResidualAnalysis:
    residuals: list[float]
    mean: float
    std: float
    skewness: float
    normality_pvalue: float
    heteroscedasticity: bool
