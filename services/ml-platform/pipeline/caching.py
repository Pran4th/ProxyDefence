import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from config import DATASET_DIR

logger = get_logger(__name__)


class PipelineCache:
    def __init__(self, cache_dir: str | None = None):
        self._cache_dir = Path(cache_dir or os.path.join(DATASET_DIR, ".pipeline_cache"))
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, Any] = {}

    def _make_key(self, step_name: str, params: dict | None = None,
                   input_hash: str | None = None) -> str:
        components = [step_name]
        if params:
            components.append(json.dumps(params, sort_keys=True))
        if input_hash:
            components.append(input_hash)
        raw = "::".join(components)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.parquet"

    def exists(self, step_name: str, params: dict | None = None,
               input_hash: str | None = None) -> bool:
        key = self._make_key(step_name, params, input_hash)
        if key in self._memory_cache:
            return True
        return self._cache_path(key).exists()

    def get(self, step_name: str, params: dict | None = None,
             input_hash: str | None = None) -> Any:
        key = self._make_key(step_name, params, input_hash)
        if key in self._memory_cache:
            logger.debug("cache hit (memory): %s", step_name)
            return self._memory_cache[key]
        cpath = self._cache_path(key)
        if cpath.exists():
            logger.debug("cache hit (disk): %s", step_name)
            result = pd.read_parquet(cpath)
            self._memory_cache[key] = result
            return result
        return None

    def set(self, step_name: str, data: Any, params: dict | None = None,
             input_hash: str | None = None):
        key = self._make_key(step_name, params, input_hash)
        self._memory_cache[key] = data
        if isinstance(data, pd.DataFrame):
            data.to_parquet(self._cache_path(key))
        else:
            import numpy as np
            if isinstance(data, np.ndarray):
                pd.DataFrame({"data": data}).to_parquet(self._cache_path(key))
            else:
                pd.DataFrame({"value": [data]}).to_parquet(self._cache_path(key))

    def invalidate(self, step_name: str | None = None):
        if step_name:
            prefix = hashlib.sha256(step_name.encode()).hexdigest()[:16]
            for f in self._cache_dir.glob(f"{prefix}*.parquet"):
                f.unlink()
            self._memory_cache = {k: v for k, v in self._memory_cache.items()
                                  if not k.startswith(prefix)}
        else:
            for f in self._cache_dir.glob("*.parquet"):
                f.unlink()
            self._memory_cache.clear()

    @property
    def size(self) -> int:
        return len(self._memory_cache) + len(list(self._cache_dir.glob("*.parquet")))

    @property
    def disk_size_bytes(self) -> int:
        return sum(f.stat().st_size for f in self._cache_dir.glob("*.parquet"))
