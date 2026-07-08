from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class EnergyInfrastructureBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "energy-service", "type": "rest_api", "category": "energy"}]

    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "capacity_mw", "type": "numerical"}, {"name": "fuel_type", "type": "categorical"}]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "criticality_score", "type": "classification"}]
