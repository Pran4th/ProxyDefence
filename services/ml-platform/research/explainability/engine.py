import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from backend.shared.logging_config import get_logger
from research.explainability.partial import PartialDependenceExplainer
from research.explainability.permutation import PermutationExplainer
from research.explainability.shap_explainer import ShapExplainer

logger = get_logger(__name__)


@dataclass
class ExplainabilityResult:
    method: str
    feature_names: list[str]
    importance_values: dict[str, float]
    importance_ranked: list[tuple[str, float]]
    shap_values: Any = None
    partial_dependence: dict | None = None
    summary_text: str | None = None
    plot_paths: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class ExplainabilityEngine:
    def __init__(self):
        self._shap_explainer: ShapExplainer | None = None
        self._permutation_explainer = PermutationExplainer()
        self._partial_explainer = PartialDependenceExplainer()

    async def explain(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray | None = None,
        method: str = "permutation",
        feature_names: list[str] | None = None,
        n_samples: int = 100,
        pool: Any = None,
    ) -> ExplainabilityResult:
        X = np.asarray(X)
        fn = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        start = time.perf_counter()

        result_data: dict[str, Any] = {}
        shap_values = None
        partial_dependence = None

        if method == "shap":
            result_data = await self.explain_shap(model, X, fn, n_samples)
            shap_values = result_data.get("shap_values")
        elif method == "permutation":
            if y is None:
                raise ValueError("y is required for permutation importance")
            result_data = await self.explain_permutation(model, X, y, n_repeats=10, feature_names=fn)
        elif method == "feature_importance":
            result_data = await self.explain_feature_importance(model, fn)
        else:
            raise ValueError(f"Unknown explanation method: {method}")

        duration = round(time.perf_counter() - start, 4)

        importance_values = result_data.get("importance_values", {})
        importance_ranked = result_data.get("importance_ranked", [])

        return ExplainabilityResult(
            method=method,
            feature_names=fn,
            importance_values=importance_values,
            importance_ranked=importance_ranked,
            shap_values=shap_values,
            partial_dependence=partial_dependence,
            duration_seconds=duration,
        )

    async def explain_shap(
        self,
        model: Any,
        X: np.ndarray,
        feature_names: list[str] | None = None,
        n_samples: int = 100,
        background_size: int = 50,
    ) -> dict[str, Any]:
        X = np.asarray(X)
        fn = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        bg_data = X[:min(background_size, X.shape[0])]

        self._shap_explainer = ShapExplainer(model, background_data=bg_data)
        result = await self._shap_explainer.compute(X, fn, n_samples)
        return result

    async def explain_permutation(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        n_repeats: int = 10,
        feature_names: list[str] | None = None,
    ) -> dict[str, Any]:
        result = await self._permutation_explainer.compute(
            model, X, y,
            n_repeats=n_repeats,
            feature_names=feature_names,
        )
        return result

    async def explain_feature_importance(
        self,
        model: Any,
        feature_names: list[str] | None = None,
    ) -> dict[str, Any]:
        fn = feature_names or []
        importance_dict: dict[str, float] = {}
        if hasattr(model, "feature_importances_"):
            fi = model.feature_importances_
            for i, name in enumerate(fn):
                if i < len(fi):
                    importance_dict[name] = round(float(fi[i]), 6)
                else:
                    importance_dict[name] = 0.0
        elif hasattr(model, "coef_"):
            coef = model.coef_
            if coef.ndim > 1:
                coef = np.abs(coef).mean(axis=0)
            else:
                coef = np.abs(coef)
            for i, name in enumerate(fn):
                if i < len(coef):
                    importance_dict[name] = round(float(coef[i]), 6)
                else:
                    importance_dict[name] = 0.0
        else:
            for name in fn:
                importance_dict[name] = 0.0

        ranked = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        return {
            "importance_values": importance_dict,
            "importance_ranked": ranked,
            "feature_names": fn,
        }

    async def explain_partial_dependence(
        self,
        model: Any,
        X: np.ndarray,
        features: list[int] | list[str],
        n_grid: int = 50,
    ) -> dict[str, Any]:
        result = await self._partial_explainer.compute(model, X, features, n_grid=n_grid)
        return result

    async def generate_summary(self, result: dict[str, Any] | ExplainabilityResult, format: str = "markdown") -> str:
        if isinstance(result, ExplainabilityResult):
            fn = result.feature_names
            ranked = result.importance_ranked
            method = result.method
        else:
            fn = result.get("feature_names", [])
            ranked = result.get("importance_ranked", [])
            method = result.get("method", "unknown")

        if format == "markdown":
            lines = []
            lines.append(f"# Explainability Summary")
            lines.append(f"**Method**: {method}")
            lines.append(f"**Features**: {len(fn)}")
            lines.append("")
            lines.append("## Feature Importance")
            lines.append("| Rank | Feature | Importance |")
            lines.append("|------|---------|------------|")
            for rank, (name, val) in enumerate(ranked[:20], 1):
                lines.append(f"| {rank} | {name} | {val:.6f} |")
            if len(ranked) > 20:
                lines.append(f"| ... | *{len(ranked) - 20} more features* | ... |")
            return "\n".join(lines)

        return f"Explainability summary using {method} with {len(fn)} features"

    async def generate_plots(self, result: dict[str, Any] | ExplainabilityResult, output_dir: str) -> list[str]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if isinstance(result, ExplainabilityResult):
            importance_values = result.importance_values
            importance_ranked = result.importance_ranked
            fn = result.feature_names
        else:
            importance_values = result.get("importance_values", {})
            importance_ranked = result.get("importance_ranked", [])
            fn = result.get("feature_names", [])

        plot_files: list[str] = []

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if importance_ranked:
            fig, ax = plt.subplots(figsize=(10, 6))
            names = [r[0] for r in importance_ranked]
            values = [r[1] for r in importance_ranked]
            colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(names)))
            ax.barh(range(len(names)), values, color=colors)
            ax.set_yticks(range(len(names)))
            ax.set_yticklabels(names)
            ax.invert_yaxis()
            ax.set_xlabel("Importance")
            ax.set_title("Feature Importance")
            plt.tight_layout()
            imp_path = str(output_path / f"importance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(imp_path, bbox_inches="tight")
            plt.close()
            plot_files.append(imp_path)

        if "shap_values" in (result if isinstance(result, dict) else {}):
            try:
                shap_vals = result.get("shap_values")
                if shap_vals is not None:
                    shap_path = str(output_path / f"shap_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png")
                    self._shap_explainer = ShapExplainer(None)
                    shap_plot_path = await self._shap_explainer.summary_plot(shap_vals, np.array([]), shap_path)
                    if shap_plot_path:
                        plot_files.append(shap_plot_path)
            except Exception as e:
                logger.warning("SHAP plot generation failed: %s", e)

        return plot_files
