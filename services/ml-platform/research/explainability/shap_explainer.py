from typing import Any

import numpy as np

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class ShapExplainer:
    def __init__(self, model: Any, background_data: np.ndarray | None = None):
        self._model = model
        self._background_data = background_data
        self._explainer = None
        self._shap_available = False
        self._try_import_shap()

    def _try_import_shap(self) -> None:
        try:
            import shap
            self._shap = shap
            self._shap_available = True
            logger.info("SHAP library loaded successfully")
        except ImportError:
            self._shap_available = False
            logger.warning("SHAP library not available; using feature_importances_ approximation")

    async def compute(
        self,
        X: np.ndarray,
        feature_names: list[str] | None = None,
        n_samples: int = 100,
    ) -> dict[str, Any]:
        X = np.asarray(X)
        n_samples = min(n_samples, X.shape[0])
        X_sample = X[:n_samples] if X.shape[0] > n_samples else X
        fn = feature_names or [f"feature_{i}" for i in range(X.shape[1])]

        if self._shap_available:
            try:
                if self._background_data is not None:
                    bg = self._background_data[:min(50, len(self._background_data))]
                else:
                    bg = X_sample[:min(50, X_sample.shape[0])]

                if hasattr(self._model, "predict_proba"):
                    explainer = self._shap.Explainer(self._model.predict_proba, bg)
                elif hasattr(self._model, "predict"):
                    explainer = self._shap.Explainer(self._model.predict, bg)
                else:
                    explainer = self._shap.Explainer(self._model, bg)

                shap_values = explainer(X_sample[:min(n_samples, 100)])

                if isinstance(shap_values, list):
                    sv = shap_values[0].values
                else:
                    sv = shap_values.values

                if sv.ndim == 1:
                    importance = np.abs(sv).mean(axis=0)
                else:
                    importance = np.abs(sv).mean(axis=0)

                if hasattr(importance, "__len__") and not isinstance(importance, np.ndarray):
                    importance = np.array(importance)

                importance_dict = {fn[i]: float(importance[i]) for i in range(len(fn)) if i < len(importance)}
                ranked = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)

                raw_values = sv.tolist() if hasattr(sv, "tolist") else sv

                return {
                    "shap_values": raw_values,
                    "feature_names": fn,
                    "importance_values": importance_dict,
                    "importance_ranked": ranked,
                    "shap_available": True,
                    "n_samples": X_sample.shape[0],
                }
            except Exception as e:
                logger.error("SHAP computation failed: %s", e)

        importance_dict, ranked = self._fallback_importance(X_sample, fn)
        return {
            "shap_values": None,
            "feature_names": fn,
            "importance_values": importance_dict,
            "importance_ranked": ranked,
            "shap_available": False,
            "n_samples": X_sample.shape[0],
            "fallback_reason": "SHAP library unavailable or computation failed",
        }

    def _fallback_importance(self, X: np.ndarray, feature_names: list[str]) -> tuple[dict[str, float], list[tuple[str, float]]]:
        importance_dict: dict[str, float] = {}
        if hasattr(self._model, "feature_importances_"):
            fi = self._model.feature_importances_
            for i, name in enumerate(feature_names):
                if i < len(fi):
                    importance_dict[name] = float(fi[i])
        elif hasattr(self._model, "coef_"):
            coef = self._model.coef_
            if coef.ndim > 1:
                coef = np.abs(coef).mean(axis=0)
            else:
                coef = np.abs(coef)
            for i, name in enumerate(feature_names):
                if i < len(coef):
                    importance_dict[name] = float(coef[i])
        else:
            for i, name in enumerate(feature_names):
                importance_dict[name] = 0.0

        if not importance_dict:
            for i, name in enumerate(feature_names):
                importance_dict[name] = 0.0

        ranked = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        return importance_dict, ranked

    async def summary_plot(self, shap_values: Any, X: np.ndarray, output_path: str) -> str:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if self._shap_available and shap_values is not None:
            try:
                self._shap.summary_plot(shap_values, X, show=False)
                plt.savefig(output_path, bbox_inches="tight")
                plt.close()
                return output_path
            except Exception:
                plt.close()

        self._make_fallback_plot(output_path, "SHAP Summary (fallback)")
        return output_path

    def _make_fallback_plot(self, output_path: str, title: str) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, title, ha="center", va="center", fontsize=14)
        ax.set_title(title)
        plt.tight_layout()
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()

    async def bar_plot(self, shap_values: Any, feature_names: list[str], output_path: str) -> str:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if self._shap_available and shap_values is not None:
            try:
                self._shap.summary_plot(shap_values, feature_names=feature_names, plot_type="bar", show=False)
                plt.savefig(output_path, bbox_inches="tight")
                plt.close()
                return output_path
            except Exception:
                plt.close()

        importance = np.abs(np.array(shap_values)).mean(axis=0) if shap_values is not None else np.zeros(len(feature_names))
        indices = np.argsort(importance)[::-1]
        fig, ax = plt.subplots(figsize=(10, 6))
        names = [feature_names[i] for i in indices]
        vals = [importance[i] for i in indices]
        ax.barh(range(len(names)), vals)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names)
        ax.invert_yaxis()
        ax.set_xlabel("mean |SHAP value|")
        ax.set_title("SHAP Bar Plot")
        plt.tight_layout()
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()
        return output_path

    async def waterfall_plot(self, shap_values: Any, X: np.ndarray, index: int, output_path: str) -> str:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if self._shap_available and shap_values is not None:
            try:
                self._shap.plots.waterfall(shap_values[index], show=False)
                plt.savefig(output_path, bbox_inches="tight")
                plt.close()
                return output_path
            except Exception:
                plt.close()

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, "Waterfall plot requires SHAP library", ha="center", va="center", fontsize=14)
        ax.set_title(f"SHAP Waterfall (index={index}) - fallback mode")
        plt.tight_layout()
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()
        return output_path
