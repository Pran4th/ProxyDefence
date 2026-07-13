"""Bootstrap ml.model_versions on a fresh deployment.

The model artifacts (data/artifacts/*/v1/model.joblib) ship with the repo --
they're just files. What a brand-new Postgres volume is missing is the
*catalog row* that tells the serving endpoints which artifact is currently
`stage='production'` for each model name.

Normally that row is written by the training scripts (train_risk_classifier.py,
tune_and_promote.py, etc.), which need real datasets and take minutes. On a
fresh host (e.g. a new AWS box) we don't want to retrain -- we want the exact,
already-verified production models this repo ships with. This script inserts
those 5 rows idempotently (ON CONFLICT DO NOTHING) so the first prediction
request works immediately, not a 503.

Metrics below are copied verbatim from this project's actual training runs
(not fabricated) -- see docs/07_ML_PROCESSES.md for what each model does.
Safe to re-run; only inserts a row if that (name, version) doesn't exist yet.
"""
from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

PRODUCTION_MODELS = [
    {
        "name": "gdelt-disruption-risk-classifier",
        "version": 7,
        "model_type": "xgboost",
        "metrics": {"val_roc_auc": 0.7458, "val_accuracy": 0.6784, "train_roc_auc": 0.784},
        "file_path": "data/artifacts/gdelt-disruption-risk-classifier/v1/model.joblib",
    },
    {
        "name": "article-topic-classifier",
        "version": 2,
        "model_type": "xgboost",
        "metrics": {"val_accuracy": 0.5866, "val_f1_weighted": 0.5634, "val_roc_auc_ovr": 0.7905},
        "file_path": "data/artifacts/article-topic-classifier/v1/model.joblib",
    },
    {
        "name": "procurement-option-ranker",
        "version": 5,
        "model_type": "xgboost_regressor",
        "metrics": {"val_r2": 0.2458, "val_mae": 0.0437, "val_rmse": 0.0632},
        "file_path": "data/artifacts/procurement-option-ranker/v1/model.joblib",
    },
    {
        "name": "fuel-price-forecaster",
        "version": 2,
        "model_type": "xgboost_regressor",
        "metrics": {"val_r2": 0.3765, "val_mae": 0.0463, "val_rmse": 0.0826},
        "file_path": "data/artifacts/fuel-price-forecaster/v1/model.joblib",
    },
    {
        "name": "brent-shock-forecaster",
        "version": 2,
        "model_type": "xgboost_regressor",
        "metrics": {"val_r2": 0.2234, "val_mae": 0.0129, "val_rmse": 0.0327},
        "file_path": "data/artifacts/brent-shock-forecaster/v1/model.joblib",
    },
]


async def main() -> None:
    dsn = (
        f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST', 'postgres')}:{os.environ.get('POSTGRES_PORT', 5432)}"
        f"/{os.environ['POSTGRES_DB']}"
    )

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    try:
        # ml.model_versions is created by ml-platform's own startup (ml_schema.sql),
        # not by Postgres init scripts -- wait for it rather than racing it.
        for attempt in range(30):
            exists = await pool.fetchval(
                "SELECT to_regclass('ml.model_versions') IS NOT NULL"
            )
            if exists:
                break
            print(f"[seed] waiting for ml.model_versions to exist (attempt {attempt + 1}/30)...")
            await asyncio.sleep(2)
        else:
            print("[seed] ml.model_versions never appeared -- is ml-platform running?", file=sys.stderr)
            sys.exit(1)

        for m in PRODUCTION_MODELS:
            row = await pool.fetchrow(
                "INSERT INTO ml.model_versions "
                "(name, version, model_type, stage, metrics, feature_version, dataset_version, "
                "artifact_path, file_path, created_by) "
                "VALUES ($1, $2, $3, 'production', $4, 1, 1, $5, $5, 'demo-seed') "
                "ON CONFLICT (name, version) DO NOTHING "
                "RETURNING name",
                m["name"], m["version"], m["model_type"], m["metrics"], m["file_path"],
            )
            print(f"[seed] {m['name']} v{m['version']}: {'inserted' if row else 'already present'}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
