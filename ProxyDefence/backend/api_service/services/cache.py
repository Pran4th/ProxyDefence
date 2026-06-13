import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int = 30) -> None:
        self.ttl_seconds = ttl_seconds
        self._values: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        cached = self._values.get(key)
        if cached is None:
            return None
        expires_at, value = cached
        if expires_at < time.time():
            self._values.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> Any:
        self._values[key] = (time.time() + self.ttl_seconds, value)
        return value


cache = TTLCache()

