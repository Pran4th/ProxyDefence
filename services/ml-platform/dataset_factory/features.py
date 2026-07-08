from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from feature_store.transforms import TRANSFORM_REGISTRY

logger = get_logger(__name__)


@dataclass
class FeatureConfig:
    name: str
    description: str = ""
    version: int = 1
    owner: str = "system"
    source_columns: list[str] = field(default_factory=list)
    transform_type: str = "identity"
    transform_params: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    freshness: str = "realtime"
    expected_range: list[float] | None = None
    null_expectations: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "owner": self.owner,
            "source_columns": self.source_columns,
            "transform_type": self.transform_type,
            "transform_params": self.transform_params,
            "dependencies": self.dependencies,
            "freshness": self.freshness,
            "expected_range": self.expected_range,
            "null_expectations": self.null_expectations,
            "tags": self.tags,
        }


FEATURE_TEMPLATES: dict[str, dict[str, Any]] = {
    "rolling_mean_7d": {
        "transform_type": "rolling_window",
        "transform_params": {"window": 7, "agg": "mean"},
        "description": "7-day rolling mean",
        "freshness": "daily",
    },
    "rolling_mean_30d": {
        "transform_type": "rolling_window",
        "transform_params": {"window": 30, "agg": "mean"},
        "description": "30-day rolling mean",
        "freshness": "daily",
    },
    "rolling_std_7d": {
        "transform_type": "rolling_window",
        "transform_params": {"window": 7, "agg": "std"},
        "description": "7-day rolling standard deviation",
        "freshness": "daily",
    },
    "rolling_sum_30d": {
        "transform_type": "rolling_window",
        "transform_params": {"window": 30, "agg": "sum"},
        "description": "30-day rolling sum",
        "freshness": "daily",
    },
    "ewma_alpha_03": {
        "transform_type": "ewma",
        "transform_params": {"alpha": 0.3},
        "description": "Exponentially weighted moving average (alpha=0.3)",
        "freshness": "realtime",
    },
    "lag_1": {
        "transform_type": "lag",
        "transform_params": {"periods": 1},
        "description": "1-period lag",
        "freshness": "realtime",
    },
    "lag_7": {
        "transform_type": "lag",
        "transform_params": {"periods": 7},
        "description": "7-period lag",
        "freshness": "realtime",
    },
    "lag_30": {
        "transform_type": "lag",
        "transform_params": {"periods": 30},
        "description": "30-period lag",
        "freshness": "realtime",
    },
    "pct_change_1d": {
        "transform_type": "identity",
        "transform_params": {},
        "description": "1-day percent change",
        "freshness": "realtime",
        "is_pct_change": True,
    },
    "pct_change_7d": {
        "transform_type": "identity",
        "transform_params": {},
        "description": "7-day percent change",
        "freshness": "realtime",
        "is_pct_change_7d": True,
    },
    "volatility_30d": {
        "transform_type": "rolling_window",
        "transform_params": {"window": 30, "agg": "std"},
        "description": "30-day volatility (rolling std)",
        "freshness": "daily",
    },
    "growth_rate": {
        "transform_type": "identity",
        "transform_params": {},
        "description": "Growth rate (log difference)",
        "freshness": "realtime",
        "is_growth_rate": True,
    },
    "frequency_encode": {
        "transform_type": "frequency_encode",
        "transform_params": {},
        "description": "Frequency encoding of categorical variable",
        "freshness": "static",
    },
    "target_encode": {
        "transform_type": "target_encode",
        "transform_params": {},
        "description": "Target encoding of categorical variable",
        "freshness": "static",
        "requires_target": True,
    },
    "count_encode": {
        "transform_type": "aggregate",
        "transform_params": {"agg_func": "count"},
        "description": "Count encoding of categorical variable",
        "freshness": "static",
    },
    "interaction_multiply": {
        "transform_type": "interaction",
        "transform_params": {"operation": "multiply"},
        "description": "Interaction feature (multiply)",
        "freshness": "realtime",
    },
    "interaction_add": {
        "transform_type": "interaction",
        "transform_params": {"operation": "add"},
        "description": "Interaction feature (add)",
        "freshness": "realtime",
    },
    "interaction_ratio": {
        "transform_type": "ratio",
        "transform_params": {},
        "description": "Ratio of two features",
        "freshness": "realtime",
    },
    "temporal_hour": {
        "transform_type": "temporal",
        "transform_params": {"features": ["hour"]},
        "description": "Hour of day from timestamp",
        "freshness": "realtime",
    },
    "temporal_dow": {
        "transform_type": "temporal",
        "transform_params": {"features": ["dow"]},
        "description": "Day of week from timestamp",
        "freshness": "realtime",
    },
    "temporal_month": {
        "transform_type": "temporal",
        "transform_params": {"features": ["month"]},
        "description": "Month from timestamp",
        "freshness": "realtime",
    },
    "temporal_quarter": {
        "transform_type": "temporal",
        "transform_params": {"features": ["quarter"]},
        "description": "Quarter from timestamp",
        "freshness": "realtime",
    },
    "temporal_weekend": {
        "transform_type": "temporal",
        "transform_params": {"features": ["weekend"]},
        "description": "Weekend flag from timestamp",
        "freshness": "realtime",
    },
    "cyclic_sin_month": {
        "transform_type": "identity",
        "transform_params": {},
        "description": "Cyclic sine encoding of month",
        "freshness": "realtime",
        "is_cyclic_sin": "month",
    },
    "cyclic_cos_month": {
        "transform_type": "identity",
        "transform_params": {},
        "description": "Cyclic cosine encoding of month",
        "freshness": "realtime",
        "is_cyclic_cos": "month",
    },
    "geospatial_distance": {
        "transform_type": "geospatial",
        "transform_params": {},
        "description": "Geospatial distance to chokepoint",
        "freshness": "static",
    },
    "standard_scale": {
        "transform_type": "standard_scale",
        "transform_params": {},
        "description": "Z-score standardization",
        "freshness": "static",
    },
    "minmax_scale": {
        "transform_type": "minmax",
        "transform_params": {},
        "description": "Min-max normalization",
        "freshness": "static",
    },
}


class FeatureEngineeringPipeline:
    def __init__(self):
        self._generated_features: dict[str, Any] = {}
        self._lineage: list[dict[str, Any]] = []

    def apply_configs(self, df: pd.DataFrame, configs: list[FeatureConfig],
                       target_column: str | None = None) -> pd.DataFrame:
        result = df.copy()
        self._lineage = []
        self._generated_features = {}

        for cfg in configs:
            if cfg.name in result.columns:
                continue
            try:
                new_col = self._apply_single_transform(result, cfg, target_column)
                if new_col is not None:
                    result[cfg.name] = new_col
                    self._generated_features[cfg.name] = cfg.to_dict()
                    self._lineage.append({
                        "feature": cfg.name,
                        "transform": cfg.transform_type,
                        "source_columns": cfg.source_columns,
                        "dependencies": cfg.dependencies,
                    })
                    logger.debug("generated feature: %s (%s)", cfg.name, cfg.transform_type)
            except Exception as e:
                logger.warning("failed to generate feature '%s': %s", cfg.name, e)

        logger.info("feature engineering complete: %d features generated", len(self._generated_features))
        return result

    def apply_template(self, df: pd.DataFrame, template_name: str,
                        source_column: str, output_name: str | None = None,
                        target_column: str | None = None,
                        extra_params: dict[str, Any] | None = None) -> pd.DataFrame:
        if template_name not in FEATURE_TEMPLATES:
            raise ValueError(f"unknown template: {template_name}. Available: {list(FEATURE_TEMPLATES.keys())}")
        tmpl = FEATURE_TEMPLATES[template_name]
        cfg = FeatureConfig(
            name=output_name or f"{source_column}_{template_name}",
            source_columns=[source_column],
            transform_type=tmpl["transform_type"],
            transform_params={**tmpl.get("transform_params", {}), **(extra_params or {})},
            description=tmpl.get("description", ""),
            freshness=tmpl.get("freshness", "realtime"),
        )
        if tmpl.get("requires_target") and target_column:
            cfg.transform_params["target_column"] = target_column

        return self.apply_configs(df, [cfg], target_column)

    def from_declarative(self, df: pd.DataFrame, feature_defs: list[dict[str, Any]],
                          target_column: str | None = None) -> pd.DataFrame:
        configs = []
        for fd in feature_defs:
            cfg = FeatureConfig(
                name=fd.get("name", "feature"),
                description=fd.get("description", ""),
                version=fd.get("version", 1),
                owner=fd.get("owner", "system"),
                source_columns=fd.get("source_columns", fd.get("sources", [])),
                transform_type=fd.get("transform", fd.get("transform_type", "identity")),
                transform_params=fd.get("params", fd.get("transform_params", {})),
                dependencies=fd.get("dependencies", []),
                freshness=fd.get("freshness", "realtime"),
                expected_range=fd.get("expected_range"),
                null_expectations=fd.get("null_expectations", 0.0),
                tags=fd.get("tags", []),
            )
            configs.append(cfg)
        return self.apply_configs(df, configs, target_column)

    def _apply_single_transform(self, df: pd.DataFrame, cfg: FeatureConfig,
                                  target_column: str | None = None) -> pd.Series | pd.DataFrame | None:
        tt = cfg.transform_type

        if tt in TRANSFORM_REGISTRY:
            transform_cls = TRANSFORM_REGISTRY[tt]
            params = dict(cfg.transform_params)
            if tt == "lag":
                transform = transform_cls(cfg.source_columns[0], **params)
            elif tt == "ratio":
                transform = transform_cls(cfg.source_columns[0], cfg.source_columns[1], **params)
            elif tt == "interaction":
                transform = transform_cls(cfg.source_columns, **params)
            elif tt == "geospatial":
                transform = transform_cls(**{**params, "output_name": cfg.name})
            elif tt == "temporal":
                transform = transform_cls(cfg.source_columns[0], **params)
            elif tt == "target_encode":
                transform = transform_cls(cfg.source_columns[0], target_column or "target", output_name=cfg.name)
            else:
                transform = transform_cls(cfg.source_columns[0], output_name=cfg.name, **params)
            transform.fit(df)
            return transform.transform(df)

        if tt == "identity":
            if cfg.source_columns:
                return df[cfg.source_columns[0]]

        params = cfg.transform_params

        if params.get("is_pct_change"):
            col = cfg.source_columns[0]
            return df[col].pct_change().fillna(0).replace([np.inf, -np.inf], 0)

        if params.get("is_pct_change_7d"):
            col = cfg.source_columns[0]
            return df[col].pct_change(periods=7).fillna(0).replace([np.inf, -np.inf], 0)

        if params.get("is_growth_rate"):
            col = cfg.source_columns[0]
            return np.log(df[col].clip(lower=1e-10)).diff().fillna(0).replace([np.inf, -np.inf], 0)

        if params.get("is_cyclic_sin"):
            col = cfg.source_columns[0]
            period = params["is_cyclic_sin"]
            period_map = {"month": 12, "hour": 24, "dow": 7, "day": 365}
            p = period_map.get(period, 12)
            return np.sin(2 * np.pi * df[col] / p)

        if params.get("is_cyclic_cos"):
            col = cfg.source_columns[0]
            period = params["is_cyclic_cos"]
            period_map = {"month": 12, "hour": 24, "dow": 7, "day": 365}
            p = period_map.get(period, 12)
            return np.cos(2 * np.pi * df[col] / p)

        logger.warning("unhandled transform type: %s for feature %s", tt, cfg.name)
        return None

    def get_generated_features(self) -> dict[str, Any]:
        return dict(self._generated_features)

    def get_lineage(self) -> list[dict[str, Any]]:
        return list(self._lineage)

    def get_catalog(self) -> dict[str, Any]:
        return {
            "features": self._generated_features,
            "lineage": self._lineage,
            "available_templates": list(FEATURE_TEMPLATES.keys()),
        }
