from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class NormalizationRule:
    name: str
    rule_type: str
    source_pattern: str | None = None
    target_format: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


@dataclass
class NormalizationResult:
    rule_name: str
    records_affected: int = 0
    changes: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class NormalizationConfig:
    max_errors: int = 10
    strict_mode: bool = False
    dry_run: bool = False
    report_changes: bool = True


class BaseNormalizer(ABC):
    def __init__(self, rule: NormalizationRule) -> None:
        self.rule = rule
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        ...

    @abstractmethod
    async def validate_rule(self) -> list[str]:
        ...

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        return {
            "total_rows": len(df),
            "estimated_affected": 0,
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }
