from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class DigitalTwinBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "energy-service", "type": "rest_api", "category": "digital_twin"}]

    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "simulation_tick", "type": "numerical"}, {"name": "node_state", "type": "categorical"}]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "supply_gap", "type": "regression"}]
