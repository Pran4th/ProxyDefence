from typing import Any

import numpy as np
from scipy.stats import normaltest, skew
from sklearn.metrics import (
    explained_variance_score,
    max_error,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from research.evaluation.results import ResidualAnalysis


def compute_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    if not mask.any():
        return float("inf")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask]))) * 100


def test_normality(residuals: np.ndarray) -> float:
    if len(residuals) < 8:
        return 1.0
    try:
        _, pvalue = normaltest(residuals)
        return float(pvalue)
    except Exception:
        return 0.0


def compute_residual_analysis(y_true: np.ndarray, y_pred: np.ndarray) -> ResidualAnalysis:
    residuals = (y_true - y_pred).flatten().tolist()
    residuals_arr = np.array(residuals)
    mean_res = float(np.mean(residuals_arr))
    std_res = float(np.std(residuals_arr))
    skewness = float(skew(residuals_arr))
    norm_pvalue = test_normality(residuals_arr)
    squared_residuals = residuals_arr ** 2
    heteroscedasticity = bool(len(residuals_arr) > 20 and np.corrcoef(np.arange(len(residuals_arr)), squared_residuals)[0, 1] > 0.3)
    return ResidualAnalysis(
        residuals=residuals,
        mean=round(mean_res, 6),
        std=round(std_res, 6),
        skewness=round(skewness, 6),
        normality_pvalue=round(norm_pvalue, 6),
        heteroscedasticity=heteroscedasticity,
    )


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    mse = mean_squared_error(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    mape = compute_mape(y_true, y_pred)
    result: dict[str, Any] = {
        "mae": round(float(mae), 6),
        "mse": round(float(mse), 6),
        "rmse": round(float(np.sqrt(mse)), 6),
        "r2": round(float(r2_score(y_true, y_pred)), 6),
        "explained_variance": round(float(explained_variance_score(y_true, y_pred)), 6),
        "max_error": round(float(max_error(y_true, y_pred)), 6),
    }
    if mape != float("inf"):
        result["mape"] = round(mape, 6)
    return result
