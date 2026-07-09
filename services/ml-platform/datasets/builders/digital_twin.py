from typing import Any
from datasets.builders.base import BaseDatasetBuilder

class DigitalTwinBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "digital-twin-scenarios", "type": "simulation", "category": "network"}]
    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "flow_capacity", "type": "numerical"}, {"name": "scenario_type", "type": "categorical"}]
    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "disruption_impact", "type": "regression"}]
