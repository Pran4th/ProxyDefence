from typing import Any

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

from research.evaluation.regression import compute_mape


def compute_smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denominator = np.abs(y_true) + np.abs(y_pred)
    mask = denominator != 0
    if not mask.any():
        return 0.0
    smape_val = 2.0 * np.mean(np.abs(y_true[mask] - y_pred[mask]) / denominator[mask])
    return round(float(smape_val * 100), 6)


def compute_mase(y_true: np.ndarray, y_pred: np.ndarray, y_train: np.ndarray | None = None, seasonal_period: int = 1) -> float:
    if y_train is None or len(y_train) < seasonal_period + 1:
        return float("nan")
    naive_errors = np.abs(np.diff(y_train, n=seasonal_period))
    if naive_errors.sum() == 0:
        return float("nan")
    mae_forecast = mean_absolute_error(y_true, y_pred)
    mae_naive = np.mean(naive_errors)
    return round(float(mae_forecast / mae_naive), 6)


def compute_rolling_window_error(y_true: np.ndarray, y_pred: np.ndarray, window: int = 5) -> float:
    n = min(len(y_true), len(y_pred))
    if n < window:
        return 0.0
    errors = []
    for i in range(0, n - window + 1):
        window_rmse = float(np.sqrt(mean_squared_error(y_true[i:i + window], y_pred[i:i + window])))
        errors.append(window_rmse)
    return round(float(np.mean(errors)), 6) if errors else 0.0


def compute_forecasting_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, y_train: np.ndarray | None = None, seasonal_period: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "smape": compute_smape(y_true, y_pred),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 6),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 6),
    }
    mape = compute_mape(y_true, y_pred)
    if mape != float("inf"):
        result["mape"] = mape
    if seasonal_period is not None:
        result["mase"] = compute_mase(y_true, y_pred, y_train, seasonal_period)
    result["rolling_window_error"] = compute_rolling_window_error(y_true, y_pred)
    return result
