from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class GraphEmbeddingsBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "energy-service", "type": "rest_api", "category": "graph"}]

    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "embedding_dim_0", "type": "numerical"}, {"name": "node_type", "type": "categorical"}]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "community_id", "type": "classification"}]
