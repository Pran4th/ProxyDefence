from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    auc,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from research.evaluation.results import ConfusionMatrix, ROCCurve


def compute_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str] | None = None) -> ConfusionMatrix:
    cm = confusion_matrix(y_true, y_pred)
    unique = labels or [str(c) for c in np.unique(np.concatenate([y_true, y_pred]))]
    matrix_list = cm.tolist()
    tp = int(np.trace(cm))
    fp = int((cm.sum(axis=0) - np.diag(cm)).sum())
    fn = int((cm.sum(axis=1) - np.diag(cm)).sum())
    tn = int(cm.sum() - (tp + fp + fn))
    return ConfusionMatrix(
        matrix=matrix_list,
        labels=unique,
        normalized=False,
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
    )


def compute_roc_curve(y_true: np.ndarray, y_score: np.ndarray, pos_label: int | str = 1) -> ROCCurve:
    fpr, tpr, thresholds = roc_curve(y_true, y_score, pos_label=pos_label)
    roc_auc = float(auc(fpr, tpr))
    return ROCCurve(
        fpr=fpr.tolist(),
        tpr=tpr.tolist(),
        thresholds=thresholds.tolist(),
        auc=roc_auc,
    )


def compute_classification_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray | None = None, average: str = "weighted",
) -> dict[str, Any]:
    unique = np.unique(y_true)
    result: dict[str, Any] = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "balanced_accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        f"precision_{average}": round(float(precision_score(y_true, y_pred, average=average, zero_division=0)), 6),
        f"recall_{average}": round(float(recall_score(y_true, y_pred, average=average, zero_division=0)), 6),
        f"f1_{average}": round(float(f1_score(y_true, y_pred, average=average, zero_division=0)), 6),
    }
    if len(unique) == 2:
        result["precision_macro"] = round(float(precision_score(y_true, y_pred, average="macro", zero_division=0)), 6)
        result["recall_macro"] = round(float(recall_score(y_true, y_pred, average="macro", zero_division=0)), 6)
        result["f1_macro"] = round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 6)
        if y_proba is not None:
            try:
                result["roc_auc"] = round(float(roc_auc_score(y_true, y_proba[:, 1])), 6)
            except Exception:
                result["roc_auc"] = None
            try:
                result["pr_auc"] = round(float(average_precision_score(y_true, y_proba[:, 1])), 6)
            except Exception:
                result["pr_auc"] = None
    elif len(unique) > 2:
        result["precision_macro"] = round(float(precision_score(y_true, y_pred, average="macro", zero_division=0)), 6)
        result["recall_macro"] = round(float(recall_score(y_true, y_pred, average="macro", zero_division=0)), 6)
        result["f1_macro"] = round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 6)
        if y_proba is not None:
            try:
                result["roc_auc_ovr"] = round(float(roc_auc_score(y_true, y_proba, multi_class="ovr")), 6)
            except Exception:
                result["roc_auc_ovr"] = None
            try:
                result["pr_auc_macro"] = round(float(average_precision_score(y_true, y_proba, average="macro")), 6)
            except Exception:
                result["pr_auc_macro"] = None
    return result


def compute_pr_curve(y_true: np.ndarray, y_score: np.ndarray) -> dict[str, Any]:
    from sklearn.metrics import precision_recall_curve
    precision_vals, recall_vals, thresholds = precision_recall_curve(y_true, y_score)
    pr_auc = float(auc(recall_vals, precision_vals))
    return {
        "precision": precision_vals.tolist(),
        "recall": recall_vals.tolist(),
        "thresholds": thresholds.tolist(),
        "pr_auc": round(pr_auc, 6),
    }
