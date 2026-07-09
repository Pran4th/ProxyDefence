from typing import Any
from datasets.builders.base import BaseDatasetBuilder
from datasets.builders.risk_signals import RiskSignalsBuilder
from datasets.builders.energy_infrastructure import EnergyInfrastructureBuilder
from datasets.builders.commodity_prices import CommodityPricesBuilder

class HybridDatasetBuilder(BaseDatasetBuilder):
    def __init__(self) -> None:
        self._components: list[BaseDatasetBuilder] = [
            RiskSignalsBuilder(), EnergyInfrastructureBuilder(), CommodityPricesBuilder(),
        ]

    def define_sources(self) -> list[dict[str, Any]]:
        return [s for c in self._components for s in c.define_sources()]

    def define_features(self) -> list[dict[str, Any]]:
        return [f for c in self._components for f in c.define_features()]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "composite_risk_score", "type": "regression"}]

    def get_dependencies(self) -> list[str]:
        return sorted({dep for c in self._components for dep in c.get_dependencies()})
