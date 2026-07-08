from typing import Any

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class FeatureImportanceExplainer:
    def __init__(self, model, feature_names: list[str]):
        self._model = model
        self._feature_names = feature_names

    def explain(self) -> dict[str, Any]:
        if hasattr(self._model, "feature_importances_"):
            importances = self._model.feature_importances_
        elif hasattr(self._model, "coef_"):
            importances = np.abs(self._model.coef_).mean(axis=0) if self._model.coef_.ndim > 1 else np.abs(self._model.coef_)
        else:
            return {"error": "model does not support feature_importances_ or coef_"}
        feat_imp = sorted(
            zip(self._feature_names, importances),
            key=lambda x: -x[1],
        )
        return {
            "type": "built_in",
            "feature_importances": [
                {"feature": f, "importance": round(float(i), 4)} for f, i in feat_imp
            ],
        }


class PermutationImportanceExplainer:
    def __init__(self, model, X_val: pd.DataFrame, y_val: pd.Series,
                 feature_names: list[str] | None = None, random_seed: int = 42):
        self._model = model
        self._X_val = X_val
        self._y_val = y_val
        self._feature_names = feature_names or list(X_val.columns)
        self._seed = random_seed

    def explain(self, n_repeats: int = 10) -> dict[str, Any]:
        result = permutation_importance(
            self._model, self._X_val, self._y_val,
            n_repeats=n_repeats, random_state=self._seed, n_jobs=-1,
        )
        feat_imp = sorted(
            zip(self._feature_names, result.importances_mean, result.importances_std),
            key=lambda x: -x[1],
        )
        return {
            "type": "permutation",
            "feature_importances": [
                {"feature": f, "importance_mean": round(float(m), 4),
                 "importance_std": round(float(s), 4)}
                for f, m, s in feat_imp
            ],
        }


class ShapExplainer:
    def __init__(self, model, X_background: pd.DataFrame | None = None):
        self._model = model
        self._X_background = X_background

    def explain(self, X_explain: pd.DataFrame) -> dict[str, Any]:
        try:
            import shap
        except ImportError:
            return {"error": "shap not installed"}

        model_type = type(self._model).__name__.lower()
        X_sample = X_explain.head(100) if len(X_explain) > 100 else X_explain

        if any(t in model_type for t in ["forest", "xgb", "lgbm", "gradient", "tree"]):
            explainer = shap.TreeExplainer(self._model)
        else:
            background = self._X_background.head(100) if self._X_background is not None and len(self._X_background) > 100 else self._X_background
            explainer = shap.KernelExplainer(self._model.predict_proba, background)

        shap_values = explainer.shap_values(X_sample)

        feature_names = list(X_explain.columns)
        if isinstance(shap_values, list):
            avg_importance = [np.abs(shap_values[c]).mean(axis=0) for c in range(len(shap_values))]
            overall = np.mean(avg_importance, axis=0)
        else:
            overall = np.abs(shap_values).mean(axis=0)

        feat_imp = sorted(
            zip(feature_names, overall),
            key=lambda x: -x[1],
        )
        return {
            "type": "shap",
            "explainer_type": type(explainer).__name__,
            "feature_importances": [
                {"feature": f, "mean_abs_shap": round(float(i), 4)} for f, i in feat_imp
            ],
        }
