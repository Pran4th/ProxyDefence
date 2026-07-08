"""create ml platform schema with feature store, model registry, experiments

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENUMS = ["feature_type", "model_stage", "model_type", "split_type"]

TABLES_IN_ORDER = [
    "feature_definitions",
    "datasets",
    "model_versions",
    "predictions",
]


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ml")

    op.execute("""
        CREATE TYPE ml.feature_type AS ENUM (
            'numerical', 'categorical', 'boolean', 'timestamp',
            'geospatial', 'entity_statistics', 'relationship_statistics',
            'historical_capacity', 'infrastructure',
            'embedding_reference', 'graph_placeholder'
        )
    """)
    op.execute("""
        CREATE TYPE ml.model_stage AS ENUM (
            'development', 'validation', 'staging', 'production', 'archived'
        )
    """)
    op.execute("""
        CREATE TYPE ml.model_type AS ENUM (
            'logistic_regression', 'decision_tree', 'random_forest',
            'xgboost', 'lightgbm', 'catboost'
        )
    """)
    op.execute("""
        CREATE TYPE ml.split_type AS ENUM ('train', 'validation', 'test')
    """)

    op.execute("""
        CREATE TABLE ml.feature_definitions (
            id BIGSERIAL PRIMARY KEY,
            uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            feature_type ml.feature_type NOT NULL,
            description TEXT,
            transform_config JSONB DEFAULT '{}',
            source_feature TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_by TEXT DEFAULT 'system',
            updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(name, version)
        )
    """)

    op.execute("""
        CREATE TABLE ml.datasets (
            id BIGSERIAL PRIMARY KEY,
            uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            path TEXT NOT NULL,
            schema_json JSONB DEFAULT '{}',
            metadata_json JSONB DEFAULT '{}',
            feature_versions JSONB DEFAULT '[]',
            total_records INTEGER,
            train_records INTEGER,
            val_records INTEGER,
            test_records INTEGER,
            target_column TEXT,
            random_seed INTEGER,
            created_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(name, version)
        )
    """)

    op.execute("""
        CREATE TABLE ml.model_versions (
            id BIGSERIAL PRIMARY KEY,
            uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            model_type ml.model_type NOT NULL,
            stage ml.model_stage NOT NULL DEFAULT 'development',
            metrics JSONB DEFAULT '{}',
            parameters JSONB DEFAULT '{}',
            feature_version INTEGER,
            dataset_version INTEGER,
            dataset_uuid UUID,
            experiment_id TEXT,
            mlflow_run_id TEXT,
            artifact_path TEXT,
            file_path TEXT,
            git_commit_hash TEXT,
            execution_time_seconds DOUBLE PRECISION,
            training_date TIMESTAMPTZ DEFAULT NOW(),
            created_by TEXT DEFAULT 'system',
            updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(name, version)
        )
    """)

    op.execute("""
        CREATE TABLE ml.predictions (
            id BIGSERIAL PRIMARY KEY,
            uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            model_version_id BIGINT REFERENCES ml.model_versions(id),
            model_name TEXT NOT NULL,
            model_version INTEGER NOT NULL,
            input_data JSONB NOT NULL,
            prediction DOUBLE PRECISION,
            confidence DOUBLE PRECISION,
            probabilities JSONB,
            latency_ms DOUBLE PRECISION,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX idx_ml_feature_active ON ml.feature_definitions(name, version)")
    op.execute("CREATE INDEX idx_ml_dataset_name ON ml.datasets(name, version)")
    op.execute("CREATE INDEX idx_ml_model_name ON ml.model_versions(name, version)")
    op.execute("CREATE INDEX idx_ml_model_stage ON ml.model_versions(name, stage) WHERE stage = 'production'")
    op.execute("CREATE INDEX idx_ml_predictions_model ON ml.predictions(model_name, model_version)")
    op.execute("CREATE INDEX idx_ml_predictions_created ON ml.predictions(created_at DESC)")


def downgrade() -> None:
    for t in reversed(TABLES_IN_ORDER):
        op.execute(f"DROP TABLE IF EXISTS ml.{t} CASCADE")
    for e in reversed(ENUMS):
        op.execute(f"DROP TYPE IF EXISTS ml.{e} CASCADE")
    op.execute("DROP SCHEMA IF EXISTS ml CASCADE")
