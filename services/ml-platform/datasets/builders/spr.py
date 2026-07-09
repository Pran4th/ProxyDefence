from typing import Any
from datasets.builders.base import BaseDatasetBuilder

class SPRBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "spr-drawdown-schedules", "type": "database", "category": "reserves"}]
    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "drawdown_rate_bpd", "type": "numerical"}, {"name": "reserve_name", "type": "categorical"}]
    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "days_to_depletion", "type": "regression"}]
