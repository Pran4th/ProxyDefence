from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class SPRBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "energy-service", "type": "rest_api", "category": "spr"}]

    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "inventory_barrels", "type": "numerical"}, {"name": "facility_type", "type": "categorical"}]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "release_strategy", "type": "classification"}]
