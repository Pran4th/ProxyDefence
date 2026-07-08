from typing import Any

from datasets.builders.base import BaseDatasetBuilder


class NewsArticlesBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "gnews-api", "type": "rest_api", "category": "news"}]

    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "title_tfidf", "type": "text"}, {"name": "source_entity", "type": "categorical"}]

    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "relevance_score", "type": "regression"}]
