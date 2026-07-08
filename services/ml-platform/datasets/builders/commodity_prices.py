from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class CommodityPricesBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "eia-petroleum", "type": "rest_api", "category": "energy"}]

    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "price_usd", "type": "numerical"}, {"name": "commodity", "type": "categorical"}]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "price_direction", "type": "classification"}]
