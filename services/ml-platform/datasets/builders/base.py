from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class BuildConfig:
    name: str
    target_column: str | None = None
    test_size: float = 0.2
    val_size: float = 0.1
    random_seed: int = 42
    feature_names: list[str] | None = None
    params: dict[str, Any] = field(default_factory=dict)

class BaseDatasetBuilder(ABC):
    @abstractmethod
    def define_sources(self) -> list[dict[str, Any]]:
        pass
    @abstractmethod
    def define_features(self) -> list[dict[str, Any]]:
        pass
    @abstractmethod
    def define_labels(self) -> list[dict[str, Any]]:
        pass
    def get_dependencies(self) -> list[str]:
        sources = self.define_sources()
        return [s.get("name", "") for s in sources if s.get("name")]
    def get_metadata(self) -> dict[str, Any]:
        return {
            "builder": self.__class__.__name__,
            "sources": self.define_sources(),
            "features": self.define_features(),
            "labels": self.define_labels(),
        }
    async def build(self, config: BuildConfig) -> dict[str, Any]:
        return {"name": config.name, "status": "built", "builder": self.__class__.__name__}
