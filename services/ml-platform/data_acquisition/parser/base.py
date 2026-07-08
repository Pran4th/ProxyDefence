from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger


@dataclass
class ParseConfig:
    source: str
    version: str
    input_path: Path
    output_path: Path
    encoding: str = "utf-8"
    batch_size: int = 10000
    max_records: int | None = None
    schema: dict | None = None
    params: dict = field(default_factory=dict)


@dataclass
class ParserResult:
    source: str
    version: str
    records_parsed: int
    records_failed: int
    output_path: Path
    schema_discovered: dict
    columns: list[str]
    row_count: int
    duration_seconds: float
    errors: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class BaseParser(ABC):
    def __init__(self) -> None:
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def parse(self, config: ParseConfig) -> ParserResult:
        ...

    @abstractmethod
    async def parse_file(
        self, input_path: Path, output_path: Path, **kwargs: Any
    ) -> ParserResult:
        ...

    @abstractmethod
    async def discover_schema(self, input_path: Path) -> dict:
        ...

    @abstractmethod
    async def validate(self, input_path: Path) -> list[str]:
        ...

    @abstractmethod
    async def get_metadata(self, input_path: Path) -> dict:
        ...

    @abstractmethod
    async def to_canonical(self, records: list[dict]) -> list[dict]:
        ...

    @property
    @abstractmethod
    def canonical_schema(self) -> dict:
        ...
