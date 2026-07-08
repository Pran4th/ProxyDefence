import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DatasetFactoryConfig:
    output_dir: str = os.getenv("DF_OUTPUT_DIR", "./data/datasets")
    report_dir: str = os.getenv("DF_REPORT_DIR", "./data/reports")
    eda_dir: str = os.getenv("DF_EDA_DIR", "./data/eda")
    export_dir: str = os.getenv("DF_EXPORT_DIR", "./data/exports")
    feature_dir: str = os.getenv("DF_FEATURE_DIR", "./data/features")

    confidence_threshold: float = float(os.getenv("DF_CONFIDENCE_THRESHOLD", "0.5"))
    null_ratio_threshold: float = float(os.getenv("DF_NULL_RATIO_THRESHOLD", "0.5"))
    outlier_iqr_multiplier: float = float(os.getenv("DF_OUTLIER_IQR_MULTIPLIER", "3.0"))
    max_missing_rate: float = float(os.getenv("DF_MAX_MISSING_RATE", "0.5"))

    default_test_size: float = float(os.getenv("DF_TEST_SIZE", "0.2"))
    default_val_size: float = float(os.getenv("DF_VAL_SIZE", "0.1"))
    random_seed: int = int(os.getenv("DF_RANDOM_SEED", "42"))

    country_normalization: bool = True
    timestamp_normalization: bool = True
    coordinate_validation: bool = True
    duplicate_detection: bool = True
    entity_resolution: bool = True
    source_reliability_scoring: bool = True

    cleaning_duplicates: bool = True
    cleaning_missing_values: bool = True
    cleaning_outliers: bool = True
    cleaning_malformed_urls: bool = True
    cleaning_utf8: bool = True
    cleaning_whitespace: bool = True
    cleaning_categorical: bool = True

    validate_schema: bool = True
    validate_primary_keys: bool = True
    validate_temporal: bool = True
    validate_country_codes: bool = True
    validate_coordinates: bool = True
    validate_categorical_domains: bool = True
    validate_entity_references: bool = True
    validate_relationships: bool = True
    validate_duplicates: bool = True
    validate_null_percentage: bool = True
    validate_feature_completeness: bool = True
    validate_target_completeness: bool = True
    validate_leakage: bool = True
    validate_grain: bool = True

    generate_quality_report: bool = True
    generate_eda: bool = True
    generate_feature_catalog: bool = True
    generate_dataset_card: bool = True
    generate_manifest: bool = True

    export_parquet: bool = True
    export_csv: bool = True
    export_metadata_json: bool = True
    export_schema_json: bool = True

    energy_service_url: str = os.getenv("ENERGY_SERVICE_URL", "http://energy-service:8000")
    kaggle_export: bool = False
    kaggle_metadata_dir: str = os.getenv("DF_KAGGLE_DIR", "./data/kaggle")

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
