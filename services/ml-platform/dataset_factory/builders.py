from __future__ import annotations

from typing import Any

from dataset_factory.framework import DatasetFactory
from dataset_factory.config import DatasetFactoryConfig


GEOPOLITICAL_RISK_INDEX_FEATURES: list[dict[str, Any]] = [
    {"name": "throughput_rolling_mean_30d", "source_columns": ["throughput_mtpa"],
     "transform": "rolling_window", "params": {"window": 30, "agg": "mean"},
     "description": "30-day rolling mean throughput"},
    {"name": "production_rolling_std_7d", "source_columns": ["production_bpd"],
     "transform": "rolling_window", "params": {"window": 7, "agg": "std"},
     "description": "7-day rolling std of production"},
    {"name": "storage_lag_1", "source_columns": ["storage_capacity_barrels"],
     "transform": "lag", "params": {"periods": 1}},
    {"name": "ports_freq_encode", "source_columns": ["num_ports_in_country"],
     "transform": "frequency_encode", "params": {}},
    {"name": "throughput_pct_change", "source_columns": ["throughput_mtpa"],
     "transform": "identity", "params": {"is_pct_change": True},
     "description": "1-period percent change in throughput"},
    {"name": "ports_interaction_refineries", "source_columns": ["num_ports_in_country", "num_refineries_in_country"],
     "transform": "interaction", "params": {"operation": "multiply"}},
    {"name": "production_growth_rate", "source_columns": ["production_bpd"],
     "transform": "identity", "params": {"is_growth_rate": True}},
    {"name": "confidence_ewma", "source_columns": ["confidence"],
     "transform": "ewma", "params": {"alpha": 0.3}},
    {"name": "region_temporal_dow", "source_columns": ["year"],
     "transform": "temporal", "params": {"features": ["dow", "month", "quarter"]},
     "description": "Temporal features from year"},
    {"name": "lat_lng_interaction", "source_columns": ["latitude", "longitude"],
     "transform": "interaction", "params": {"operation": "multiply"}},
    {"name": "distance_to_hormuz", "source_columns": ["latitude"],
     "transform": "geospatial", "params": {"lat_col": "latitude", "lng_col": "longitude", "chokepoint": "hormuz"}},
    {"name": "risk_volatility_30d", "source_columns": ["criticality_score"],
     "transform": "rolling_window", "params": {"window": 30, "agg": "std"}},
    {"name": "org_type_standard_scale", "source_columns": ["num_ports_in_country"],
     "transform": "standard_scale", "params": {}},
    {"name": "production_robust_scale", "source_columns": ["production_bpd"],
     "transform": "robust_scale", "params": {}},
    {"name": "country_capacity_ratio", "source_columns": ["total_oil_production_bpd", "num_refineries_in_country"],
     "transform": "ratio", "params": {"fill_value": 0.0},
     "description": "Production to refinery ratio"},
]

ENERGY_CRITICALITY_FEATURES: list[dict[str, Any]] = [
    {"name": "prod_capacity_ratio", "source_columns": ["production_bpd", "storage_capacity_barrels"],
     "transform": "ratio", "params": {"fill_value": 0.0}},
    {"name": "infra_density", "source_columns": ["num_ports_in_country", "num_refineries_in_country"],
     "transform": "interaction", "params": {"operation": "add"}},
    {"name": "throughput_zscore", "source_columns": ["throughput_mtpa"],
     "transform": "standard_scale", "params": {}},
    {"name": "region_freq", "source_columns": ["region"],
     "transform": "frequency_encode", "params": {}},
    {"name": "org_freq", "source_columns": ["organization_type"],
     "transform": "frequency_encode", "params": {}},
    {"name": "production_log", "source_columns": ["production_bpd"],
     "transform": "identity", "params": {"is_growth_rate": False}},
]

SUPPLY_CHAIN_RISK_FEATURES: list[dict[str, Any]] = [
    {"name": "chokepoint_distance_min", "source_columns": ["latitude"],
     "transform": "geospatial", "params": {"chokepoint": "hormuz",
      "lat_col": "latitude", "lng_col": "longitude"}},
    {"name": "chokepoint_distance_malacca", "source_columns": ["latitude"],
     "transform": "geospatial", "params": {"chokepoint": "malacca",
      "lat_col": "latitude", "lng_col": "longitude"}},
    {"name": "chokepoint_distance_suez", "source_columns": ["latitude"],
     "transform": "geospatial", "params": {"chokepoint": "suez",
      "lat_col": "latitude", "lng_col": "longitude"}},
    {"name": "port_density_score", "source_columns": ["num_ports_in_country", "num_refineries_in_country"],
     "transform": "ratio", "params": {"fill_value": 0.0}},
    {"name": "risk_ewma", "source_columns": ["criticality_score"],
     "transform": "ewma", "params": {"alpha": 0.2}},
    {"name": "throughput_volatility", "source_columns": ["throughput_mtpa"],
     "transform": "rolling_window", "params": {"window": 7, "agg": "std"}},
]


PRESET_DATASETS: dict[str, dict[str, Any]] = {
    "geopolitical_risk_index_v1": {
        "name": "geopolitical_risk_index",
        "target_column": "criticality_score",
        "feature_configs": GEOPOLITICAL_RISK_INDEX_FEATURES,
        "description": "Geopolitical Risk Index dataset with engineered features for energy infrastructure risk assessment",
        "dataset_type": "energy_infrastructure",
    },
    "energy_criticality_v1": {
        "name": "energy_criticality",
        "target_column": "criticality_score",
        "feature_configs": ENERGY_CRITICALITY_FEATURES,
        "description": "Energy infrastructure criticality classification dataset",
        "dataset_type": "energy_infrastructure",
    },
    "supply_chain_risk_v1": {
        "name": "supply_chain_risk",
        "target_column": "criticality_score",
        "feature_configs": SUPPLY_CHAIN_RISK_FEATURES,
        "description": "Supply chain risk assessment dataset with chokepoint distance features",
        "dataset_type": "energy_infrastructure",
    },
}


async def build_preset(preset_name: str, **overrides) -> dict[str, Any]:
    if preset_name not in PRESET_DATASETS:
        available = list(PRESET_DATASETS.keys())
        raise ValueError(f"Unknown preset '{preset_name}'. Available: {available}")
    preset = PRESET_DATASETS[preset_name]
    config = DatasetFactoryConfig()
    factory = DatasetFactory(config)

    params = {**preset, **overrides}
    params.pop("name", None)
    params.pop("feature_configs", None)

    result = await factory.build(
        name=preset["name"],
        target_column=preset["target_column"],
        feature_configs=preset["feature_configs"],
        description=preset.get("description"),
        dataset_type=preset.get("dataset_type", "energy_infrastructure"),
        **overrides,
    )
    return result.to_dict()
