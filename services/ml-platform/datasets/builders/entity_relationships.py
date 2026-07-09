from typing import Any
from datasets.builders.base import BaseDatasetBuilder

class EntityRelationshipsBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "entity-relationships", "type": "database", "category": "graph"}]
    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "relationship_strength", "type": "numerical"}, {"name": "relationship_type", "type": "categorical"}]
    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "relationship_valid", "type": "classification"}]
