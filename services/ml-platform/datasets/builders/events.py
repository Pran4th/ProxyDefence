from typing import Any
from datasets.builders.base import BaseDatasetBuilder

class EventsBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "gdelt-events", "type": "rest_api", "category": "geopolitical"}]
    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "avg_tone", "type": "numerical"}, {"name": "actor_country", "type": "categorical"}]
    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "event_severity", "type": "classification"}]
