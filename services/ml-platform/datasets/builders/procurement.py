from typing import Any
from datasets.builders.base import BaseDatasetBuilder

class ProcurementBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "procurement-options", "type": "database", "category": "supply_chain"}]
    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "supplier_score", "type": "numerical"}, {"name": "crude_grade", "type": "categorical"}]
    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "composite_rank", "type": "ranking"}]
