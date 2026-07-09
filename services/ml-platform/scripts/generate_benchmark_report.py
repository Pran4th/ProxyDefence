"""Wires up the platform's own leaderboard (research/leaderboard/board.py, persists
to the real ml.leaderboard table) and evaluation reporter (evaluation/reporter.py,
writes JSON+MD to data/reports/) — both real, both previously never called by
anything. Reads every row in ml.model_versions and feeds it into both.

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/generate_benchmark_report.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from backend.shared.settings import settings  # noqa: E402
from research.leaderboard.board import Leaderboard, RankingEntry  # noqa: E402
from evaluation.reporter import EvaluationReporter  # noqa: E402

# model_name -> (primary_metric key in stored metrics, secondary_metric key).
# Primary must be a "higher is better" metric since the leaderboard sorts DESC —
# R² and AUC qualify; MAE/RMSE (lower is better) are relegated to secondary.
PRIMARY_METRIC_MAP: dict[str, tuple[str, str]] = {
    "gdelt-disruption-risk-classifier": ("val_roc_auc", "val_accuracy"),
    "procurement-option-ranker": ("val_r2", "val_mae"),
    "fuel-price-forecaster": ("val_r2", "val_mae"),
    "brent-shock-forecaster": ("val_r2", "val_mae"),
}


async def main() -> None:
    host = settings.POSTGRES_HOST if settings.POSTGRES_HOST != "postgres" else "localhost"
    pool = await asyncpg.create_pool(
        host=host, port=settings.POSTGRES_PORT, user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD, database=settings.POSTGRES_DB,
        min_size=1, max_size=2,
    )

    rows = await pool.fetch(
        "SELECT * FROM ml.model_versions WHERE stage != 'archived' ORDER BY name, version"
    )
    print(f"found {len(rows)} non-archived model versions in ml.model_versions")

    leaderboard = Leaderboard()
    reporter = EvaluationReporter(output_dir="./data/reports")
    written = []

    for row in rows:
        name = row["name"]
        metrics_raw = row["metrics"]
        metrics = json.loads(metrics_raw) if isinstance(metrics_raw, str) else (metrics_raw or {})
        primary_key, secondary_key = PRIMARY_METRIC_MAP.get(name, (None, None))

        if primary_key is None or primary_key not in metrics:
            print(f"  [skip leaderboard] {name} v{row['version']}: no primary metric mapping for this model")
            primary_score, secondary_score = 0.0, 0.0
            primary_key, secondary_key = "unmapped", "unmapped"
        else:
            primary_score = float(metrics[primary_key])
            secondary_score = float(metrics.get(secondary_key, 0.0))

        entry = RankingEntry(
            model_name=name,
            model_version=row["version"],
            model_type=row["model_type"],
            experiment_name="ml-platform-benchmark",
            run_id=str(row["mlflow_run_id"] or row["uuid"]),
            primary_metric=primary_key,
            primary_score=primary_score,
            secondary_metric=secondary_key,
            secondary_score=secondary_score,
            training_time_seconds=float(row["execution_time_seconds"] or 0.0),
            dataset_name=name,
            dataset_version=row["dataset_version"] or 1,
            feature_version=row["feature_version"] or 1,
            params=row["parameters"] or {},
            tags=[row["stage"]],
        )
        entry_id = await leaderboard.add_entry(entry, pool=pool)
        print(f"  [leaderboard] {entry_id}: {primary_key}={primary_score:.4f} {secondary_key}={secondary_score:.4f} stage={row['stage']}")

        report = reporter.generate_report(
            metrics={k: v for k, v in metrics.items() if isinstance(v, (int, float))},
            model_name=name, model_version=row["version"],
            dataset_version=row["dataset_version"], feature_version=row["feature_version"],
            execution_time=row["execution_time_seconds"],
            extra={"stage": row["stage"], "model_type": row["model_type"]},
        )
        json_path, md_path = reporter.save_report(report, filename=f"{name}_v{row['version']}")
        written.append(json_path)
        print(f"  [report] {md_path}")

    print(f"\nleaderboard entries written: {len(rows)}")
    print(f"report files written: {len(written)}")

    print("\n" + "=" * 70)
    print("LEADERBOARD — all models, by dataset-appropriate primary metric")
    print("=" * 70)
    for name in PRIMARY_METRIC_MAP:
        history = await leaderboard.get_model_history(name, pool=pool)
        if not history:
            continue
        best = max(history, key=lambda e: e.primary_score)
        print(f"{name}: best={best.primary_metric}={best.primary_score:.4f} "
              f"(v{best.model_version}, {len(history)} version(s) tracked)")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
