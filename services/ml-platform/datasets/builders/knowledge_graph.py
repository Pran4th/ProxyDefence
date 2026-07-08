from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class KnowledgeGraphBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "energy-service", "type": "rest_api", "category": "knowledge_graph"}]

    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "node_degree", "type": "numerical"}, {"name": "edge_type", "type": "categorical"}]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "relationship_strength", "type": "regression"}]
