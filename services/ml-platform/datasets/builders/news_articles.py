from typing import Any
from datasets.builders.base import BaseDatasetBuilder

class NewsArticlesBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict[str, Any]]:
        return [{"name": "gnews", "type": "rest_api", "category": "news"}]
    def define_features(self) -> list[dict[str, Any]]:
        return [{"name": "tfidf_headline", "type": "text"}, {"name": "sentiment_score", "type": "numerical"}]
    def define_labels(self) -> list[dict[str, Any]]:
        return [{"name": "topic", "type": "classification"}]
