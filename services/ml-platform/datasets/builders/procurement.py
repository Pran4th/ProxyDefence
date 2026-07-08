from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class ProcurementBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "energy-service", "type": "rest_api", "category": "procurement"}]

    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "cost_per_bbl", "type": "numerical"}, {"name": "supplier_region", "type": "categorical"}]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "supplier_score", "type": "regression"}]
