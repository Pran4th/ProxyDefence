from typing import Any
from datasets.builders.base import BaseDatasetBuilder

class EnergyInfrastructureBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "energy-service-catalog", "type": "rest_api", "category": "infrastructure"}]
    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "throughput_mtpa", "type": "numerical"}, {"name": "region", "type": "categorical"}]
    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "criticality_score", "type": "classification"}]
