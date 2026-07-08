from typing import Any

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    k = min(k, len(y_score))
    if k == 0:
        return 0.0
    top_k_idx = np.argsort(y_score)[-k:]
    top_k_true = y_true[top_k_idx]
    return float(top_k_true.sum()) / k


def compute_anomaly_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray | None = None) -> dict[str, Any]:
    unique = np.unique(y_true)
    result: dict[str, Any] = {
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 6),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 6),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }
    anomaly_ratio = float(y_true.sum()) / len(y_true)
    expected_anomalies = max(1, int(anomaly_ratio * len(y_true)))
    result["precision_at_k"] = round(compute_precision_at_k(y_true, y_pred, expected_anomalies), 6)
    result["average_precision"] = round(float(average_precision_score(y_true, y_pred)), 6)
    if y_score is not None and len(unique) == 2:
        try:
            result["roc_auc"] = round(float(roc_auc_score(y_true, y_score)), 6)
        except Exception:
            result["roc_auc"] = None
    return result
