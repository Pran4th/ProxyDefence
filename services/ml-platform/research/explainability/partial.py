from typing import Any

import numpy as np
from sklearn.inspection import PartialDependenceDisplay

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class PartialDependenceExplainer:
    async def compute(
        self,
        model: Any,
        X: np.ndarray,
        features: list[int] | list[str],
        n_grid: int = 50,
        kind: str = "average",
    ) -> dict[str, Any]:
        X = np.asarray(X)
        feature_indices: list[int] = []
        feature_labels: list[str] = []

        for f in features:
            if isinstance(f, str) and f.startswith("feature_"):
                idx = int(f.split("_")[1])
                feature_indices.append(idx)
                feature_labels.append(f)
            elif isinstance(f, int):
                feature_indices.append(f)
                feature_labels.append(f"feature_{f}")
            else:
                feature_indices.append(0)
                feature_labels.append(str(f))

        try:
            from sklearn.inspection import partial_dependence

            results: dict[str, Any] = {
                "feature_labels": feature_labels,
                "feature_indices": feature_indices,
                "grids": [],
                "averages": [],
                "kind": kind,
            }

            for idx in feature_indices:
                pd_result = partial_dependence(model, X, [idx], grid_resolution=n_grid, kind=kind)
                results["grids"].append(pd_result["grid_values"][0].tolist())
                results["averages"].append(pd_result["average"][0].tolist() if hasattr(pd_result["average"][0], "tolist") else pd_result["average"][0])

            return results

        except Exception as e:
            logger.error("Partial dependence computation failed: %s", e)
            return {
                "feature_labels": feature_labels,
                "feature_indices": feature_indices,
                "grids": [],
                "averages": [],
                "kind": kind,
                "error": str(e),
            }

    async def plot(self, results: dict[str, Any], output_path: str) -> str:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        grids = results.get("grids", [])
        averages = results.get("averages", [])
        labels = results.get("feature_labels", [f"feature_{i}" for i in range(len(grids))])

        n_features = len(grids)
        if n_features == 0:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, "No partial dependence data available", ha="center", va="center", fontsize=14)
            plt.tight_layout()
            plt.savefig(output_path, bbox_inches="tight")
            plt.close()
            return output_path

        n_cols = min(3, n_features)
        n_rows = (n_features + n_cols - 1) // n_cols
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 5 * n_rows))
        if n_rows == 1 and n_cols == 1:
            axes = np.array([axes])
        axes_flat = axes.flatten()

        for i in range(n_features):
            ax = axes_flat[i]
            grid = grids[i]
            avg = averages[i]
            ax.plot(grid, avg, "b-", linewidth=2)
            ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
            ax.set_xlabel(labels[i] if i < len(labels) else f"feature_{i}")
            ax.set_ylabel("Partial dependence")
            ax.set_title(f"PDP: {labels[i] if i < len(labels) else f'feature_{i}'}")
            ax.grid(True, alpha=0.3)

        for j in range(i + 1, len(axes_flat)):
            axes_flat[j].set_visible(False)

        plt.tight_layout()
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()

        logger.info("partial dependence plot saved to %s", output_path)
        return output_path
