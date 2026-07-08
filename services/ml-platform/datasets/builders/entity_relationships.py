from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class EntityRelationshipsBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "energy-service", "type": "rest_api", "category": "relationships"}]

    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "relationship_type", "type": "categorical"}, {"name": "entity_count", "type": "numerical"}]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "relationship_strength", "type": "regression"}]
