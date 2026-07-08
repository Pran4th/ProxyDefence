from __future__ import annotations

import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule

logger = get_logger(__name__)


class NormalizationRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, type[BaseNormalizer]] = {}

    def register(self, rule_type: str, normalizer_class: type[BaseNormalizer]) -> None:
        self._registry[rule_type] = normalizer_class
        logger.info("registered_normalizer", rule_type=rule_type, normalizer=normalizer_class.__name__)

    def get(self, rule_type: str) -> type[BaseNormalizer]:
        if rule_type not in self._registry:
            raise KeyError(f"no normalizer registered for rule_type={rule_type!r}")
        return self._registry[rule_type]

    def create(self, rule: NormalizationRule) -> BaseNormalizer:
        normalizer_class = self.get(rule.rule_type)
        return normalizer_class(rule)

    def list_types(self) -> list[str]:
        return list(self._registry.keys())

    async def apply_all(
        self,
        df: pd.DataFrame,
        rules: list[NormalizationRule],
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, list[NormalizationResult]]:
        results: list[NormalizationResult] = []
        for rule in rules:
            normalizer = self.create(rule)
            df, result = await normalizer.normalize(df, config)
            results.append(result)
        return df, results

    async def apply_sequential(
        self,
        df: pd.DataFrame,
        rule_sequence: list[str],
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, list[NormalizationResult]]:
        results: list[NormalizationResult] = []
        for rule_type in rule_sequence:
            normalizer_class = self.get(rule_type)
            rule = NormalizationRule(name=rule_type, rule_type=rule_type)
            normalizer = normalizer_class(rule)
            df, result = await normalizer.normalize(df, config)
            results.append(result)
        return df, results


normalization_registry = NormalizationRegistry()
