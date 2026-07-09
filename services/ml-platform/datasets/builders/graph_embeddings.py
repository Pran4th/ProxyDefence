from typing import Any
from datasets.builders.base import BaseDatasetBuilder

class GraphEmbeddingsBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "entity-relationships", "type": "database", "category": "graph"}]
    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "embedding_vector", "type": "numerical"}, {"name": "node_type", "type": "categorical"}]
    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "cluster_id", "type": "clustering"}]
