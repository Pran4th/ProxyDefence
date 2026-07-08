import time
from collections import OrderedDict
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class FeatureCache:
    def __init__(self, capacity: int = 1000, ttl_seconds: int = 300):
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._capacity = capacity
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def _make_key(self, entity_type: str, entity_id: str, feature_version: int) -> str:
        return f"{entity_type}:{entity_id}:v{feature_version}"

    def get(self, entity_type: str, entity_id: str, feature_version: int) -> dict[str, Any] | None:
        key = self._make_key(entity_type, entity_id, feature_version)
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.time() - entry["ts"] > self._ttl:
            self._cache.pop(key)
            self._misses += 1
            return None
        self._cache.move_to_end(key)
        self._hits += 1
        return entry["data"]

    def set(self, entity_type: str, entity_id: str, feature_version: int, data: dict[str, Any]):
        key = self._make_key(entity_type, entity_id, feature_version)
        while len(self._cache) >= self._capacity:
            self._cache.popitem(last=False)
        self._cache[key] = {"data": data, "ts": time.time()}

    def invalidate(self, entity_type: str | None = None, entity_id: str | None = None):
        if entity_type and entity_id:
            keys = [k for k in self._cache if k.startswith(f"{entity_type}:{entity_id}")]
        elif entity_type:
            keys = [k for k in self._cache if k.startswith(f"{entity_type}:")]
        else:
            keys = list(self._cache.keys())
        for k in keys:
            self._cache.pop(k, None)

    def invalidate_all(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def capacity(self) -> int:
        return self._capacity


_feature_cache: FeatureCache | None = None


def get_feature_cache() -> FeatureCache:
    global _feature_cache
    if _feature_cache is None:
        _feature_cache = FeatureCache()
    return _feature_cache
