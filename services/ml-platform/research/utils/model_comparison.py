from typing import Any

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class ModelComparison:
    def __init__(self):
        self._results: list[dict[str, Any]] = []

    def add_result(self, model_name: str, metrics: dict[str, float],
                    params: dict[str, Any] | None = None,
                    run_id: str | None = None,
                    tags: dict[str, str] | None = None):
        self._results.append({
            "model_name": model_name,
            "metrics": metrics,
            "params": params or {},
            "run_id": run_id,
            "tags": tags or {},
        })

    def get_leaderboard(self, metric: str = "f1", higher_is_better: bool = True) -> list[dict]:
        valid = [r for r in self._results if metric in r["metrics"]]
        sorted_results = sorted(
            valid, key=lambda x: x["metrics"][metric], reverse=higher_is_better
        )
        return [
            {
                "rank": i + 1,
                "model_name": r["model_name"],
                metric: r["metrics"][metric],
                "all_metrics": r["metrics"],
                "run_id": r["run_id"],
            }
            for i, r in enumerate(sorted_results)
        ]

    def get_comparison_table(self) -> pd.DataFrame:
        rows = []
        for r in self._results:
            row = {"model_name": r["model_name"], "run_id": r["run_id"]}
            row.update(r["metrics"])
            rows.append(row)
        df = pd.DataFrame(rows)
        meta_cols = ["model_name", "run_id"]
        metric_cols = [c for c in df.columns if c not in meta_cols]
        df = df[meta_cols + metric_cols]
        return df

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_models": len(self._results),
            "results": [
                {
                    "model_name": r["model_name"],
                    "metrics": r["metrics"],
                    "params": r["params"],
                }
                for r in self._results
            ],
        }
