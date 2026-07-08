from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class HybridDatasetBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [
            {"name": "energy-service", "type": "rest_api", "category": "energy"},
            {"name": "gdelt-events", "type": "rest_api", "category": "geopolitical"},
        ]

    def define_features(self) -> list[dict[str, Any]]:
        return [
            {"name": "capacity_mw", "type": "numerical"},
            {"name": "goldstein_scale", "type": "numerical"},
            {"name": "region", "type": "categorical"},
        ]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "criticality_score", "type": "classification"}]
