from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from config import REPORT_DIR

logger = get_logger(__name__)


class PlotManager:
    def __init__(self, output_dir: str | None = None):
        self._output_dir = Path(output_dir or f"{REPORT_DIR}/plots")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._generated: list[str] = []

    @property
    def generated_plots(self) -> list[str]:
        return list(self._generated)

    def _save(self, name: str) -> str:
        self._generated.append(name)
        path = str(self._output_dir / name)
        return path

    def save_histogram(self, data: np.ndarray, name: str, bins: int = 30, title: str = ""):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(data, bins=bins, edgecolor="black", alpha=0.7)
            ax.set_title(title or f"Histogram: {name}")
            ax.set_xlabel("Value")
            ax.set_ylabel("Frequency")
            path = self._output_dir / f"{name}_histogram.png"
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            self._generated.append(str(path))
        except ImportError:
            logger.warning("matplotlib not available, skipping histogram")

    def save_correlation_matrix(self, df: pd.DataFrame, name: str, title: str = ""):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import seaborn as sns
            numeric_df = df.select_dtypes(include=[np.number])
            if numeric_df.shape[1] < 2:
                return
            corr = numeric_df.corr()
            fig, ax = plt.subplots(figsize=(12, 10))
            sns.heatmap(corr, annot=False, cmap="RdBu_r", center=0, ax=ax)
            ax.set_title(title or f"Correlation Matrix: {name}")
            path = self._output_dir / f"{name}_correlation.png"
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            self._generated.append(str(path))
        except ImportError:
            logger.warning("seaborn not available, skipping correlation matrix")

    def save_feature_importance(self, importance_dict: dict[str, float],
                                  name: str, title: str = ""):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            items = sorted(importance_dict.items(), key=lambda x: -x[1])[:20]
            features, scores = zip(*items) if items else ([], [])
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.barh(range(len(features)), scores, color="steelblue")
            ax.set_yticks(range(len(features)))
            ax.set_yticklabels(features)
            ax.set_title(title or f"Feature Importance: {name}")
            ax.set_xlabel("Importance")
            path = self._output_dir / f"{name}_importance.png"
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            self._generated.append(str(path))
        except ImportError:
            logger.warning("matplotlib not available, skipping feature importance chart")

    def save_distribution_comparison(self, expected: np.ndarray, actual: np.ndarray,
                                       name: str, title: str = ""):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(expected, bins=30, alpha=0.5, label="Expected", density=True)
            ax.hist(actual, bins=30, alpha=0.5, label="Actual", density=True)
            ax.set_title(title or f"Distribution Comparison: {name}")
            ax.legend()
            path = self._output_dir / f"{name}_distribution_comparison.png"
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            self._generated.append(str(path))
        except ImportError:
            logger.warning("matplotlib not available, skipping distribution comparison")
