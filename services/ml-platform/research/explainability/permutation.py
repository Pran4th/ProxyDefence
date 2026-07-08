from typing import Any, Callable

import numpy as np
from sklearn.inspection import permutation_importance as sk_permutation_importance

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class PermutationExplainer:
    async def compute(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        n_repeats: int = 10,
        scoring: str | Callable | None = None,
        feature_names: list[str] | None = None,
        random_state: int = 42,
    ) -> dict[str, Any]:
        X = np.asarray(X)
        y = np.asarray(y)
        fn = feature_names or [f"feature_{i}" for i in range(X.shape[1])]

        try:
            result = sk_permutation_importance(
                model, X, y,
                n_repeats=n_repeats,
                scoring=scoring,
                random_state=random_state,
            )
        except Exception as e:
            logger.error("Permutation importance failed: %s", e)
            return {
                "importance_values": {name: 0.0 for name in fn},
                "importance_ranked": [(name, 0.0) for name in fn],
                "importances_std": {name: 0.0 for name in fn},
                "feature_names": fn,
                "error": str(e),
            }

        importance_mean = result.importances_mean
        importance_std = result.importances_std

        importance_dict = {
            fn[i]: round(float(importance_mean[i]), 6) for i in range(len(fn)) if i < len(importance_mean)
        }
        std_dict = {
            fn[i]: round(float(importance_std[i]), 6) for i in range(len(fn)) if i < len(importance_std)
        }
        ranked = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)

        return {
            "importance_values": importance_dict,
            "importance_ranked": ranked,
            "importances_std": std_dict,
            "importances_raw": result.importances.tolist() if hasattr(result.importances, "tolist") else None,
            "feature_names": fn,
            "n_repeats": n_repeats,
        }

    async def plot(self, importance: dict[str, Any] | list[tuple[str, float]], feature_names: list[str] | None, output_path: str) -> str:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if isinstance(importance, dict):
            if "importance_ranked" in importance:
                ranked = importance["importance_ranked"]
            elif "importance_values" in importance:
                ranked = sorted(importance["importance_values"].items(), key=lambda x: x[1], reverse=True)
            else:
                ranked = [(name, 0.0) for name in feature_names] if feature_names else []
        elif isinstance(importance, list):
            ranked = sorted(importance, key=lambda x: x[1], reverse=True)
        else:
            ranked = [(name, 0.0) for name in (feature_names or ["?"])]

        names = [r[0] for r in ranked]
        values = [r[1] for r in ranked]

        fig, ax = plt.subplots(figsize=(10, 6))
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(names)))
        ax.barh(range(len(names)), values, color=colors)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names)
        ax.invert_yaxis()
        ax.set_xlabel("Importance")
        ax.set_title("Permutation Feature Importance")
        plt.tight_layout()
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()

        logger.info("permutation importance plot saved to %s", output_path)
        return output_path
