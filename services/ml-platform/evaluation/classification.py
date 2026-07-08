from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)


def evaluate_classification(y_true: np.ndarray, y_pred: np.ndarray,
                            y_proba: np.ndarray | None = None,
                            labels: list | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_weighted": round(float(precision_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "recall_weighted": round(float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "f1_weighted": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "classification_report": classification_report(y_true, y_pred, output_dict=True, zero_division=0),
    }

    unique = np.unique(y_true)
    if y_proba is not None and len(unique) == 2:
        try:
            result["roc_auc"] = round(float(roc_auc_score(y_true, y_proba[:, 1])), 4)
        except Exception:
            result["roc_auc"] = None
    elif y_proba is not None and len(unique) > 2:
        try:
            result["roc_auc_ovr"] = round(float(roc_auc_score(y_true, y_proba, multi_class="ovr")), 4)
        except Exception:
            result["roc_auc_ovr"] = None

    return result
