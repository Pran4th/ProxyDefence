from typing import Any
from datasets.builders.base import BaseDatasetBuilder

class RiskSignalsBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "gdelt-events", "type": "rest_api", "category": "geopolitical"}]
    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "goldstein_scale", "type": "numerical"}, {"name": "event_type", "type": "categorical"}]
    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "escalation_flag", "type": "classification"}]
