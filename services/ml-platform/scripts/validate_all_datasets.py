"""Runs the existing (previously-disconnected) validation + quality tooling
against every dataset registered in ml.dataset_catalog, and persists results
to ml.dataset_validations / ml.dataset_profiles.

Canonical entity-schema datasets (entity_type/entity_id/.../attributes/metadata)
store their real substantive fields (price, capacity, sanction program, vessel
counts, ...) as a JSON string inside the `attributes` column. Validating the
raw CSV as-is would only ever see lat/lon/confidence — the flattening step
below (json_normalize on `attributes`) is what makes missing-value/outlier/
validity checks actually meaningful for this schema.

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/validate_all_datasets.py
"""
from __future__ import annotations

import ast
import asyncio
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from backend.shared.settings import settings  # noqa: E402
from datasets.validation import DatasetValidationPipeline, full_validators  # noqa: E402
from dataset_factory.quality import QualityReportGenerator  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED = REPO_ROOT / "datasets" / "processed"

# name -> (csv path, version) as registered in ml.dataset_catalog this session.
# dataset_catalog has UNIQUE(name), so multi-version sources (e.g. global-fuel-prices)
# are validated against their latest/most-complete file.
DATASETS: dict[str, tuple[Path, int]] = {
    "ofac-sanctions": (PROCESSED / "ofac-sanctions/2026-07-09/ofac-sanctions.csv", 1),
    "global-ports": (PROCESSED / "world-port-index/2026-07-09/world-port-index.csv", 1),
    "global-fuel-prices": (PROCESSED / "commodity-prices/2026/commodity-prices.csv", 2),
    "gem-oil-ngl-pipelines": (PROCESSED / "gem-infrastructure/oil-ngl-pipelines/oil-ngl-pipelines.csv", 1),
    "gem-gas-pipelines": (PROCESSED / "gem-infrastructure/gas-pipelines/gas-pipelines.csv", 1),
    "gem-lng-terminals": (PROCESSED / "gem-infrastructure/lng-terminals/lng-terminals.csv", 1),
    "gem-oil-gas-fields": (PROCESSED / "gem-infrastructure/oil-gas-fields/oil-gas-fields.csv", 1),
    "gem-oil-gas-plants": (PROCESSED / "gem-infrastructure/oil-gas-plants/oil-gas-plants.csv", 1),
    "gdelt-events": (PROCESSED / "gdelt-merged/gdelt-events-sample.csv", 1),
    "procurement-options": (PROCESSED / "procurement/procurement-options.csv", 1),
    "spr-drawdown-schedules": (PROCESSED / "spr/spr-drawdown-schedules.csv", 1),
    "india-crude-imports": (PROCESSED / "un_comtrade/india-crude-imports-multiyear.csv", 2),
    "country-energy-indicators": (PROCESSED / "world_bank/country-energy-indicators.csv", 1),
    "brent-daily": (PROCESSED / "fred-oil-prices/brent_daily/fred-oil-prices.csv", 1),
    "wti-daily": (PROCESSED / "fred-oil-prices/wti_daily/fred-oil-prices.csv", 1),
    "eu-sanctions": (PROCESSED / "eu-sanctions/eu-sanctions.csv", 1),
    "opensanctions": (PROCESSED / "opensanctions/opensanctions-filtered.csv", 1),
    "eia-crude-stocks": (PROCESSED / "eia-crude-stocks/eia-crude-stocks.csv", 1),
    "crude-price-api": (PROCESSED / "crude-price-api/crude-price-api.csv", 1),
    "ais-chokepoints": (PROCESSED / "ais-chokepoints/ais-chokepoints.csv", 1),
}

CANONICAL_JSON_COLS = ("attributes", "metadata", "relationships")


def _safe_parse(value: object) -> object:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return None


def _make_hashable(value: object) -> object:
    """List/dict cells (e.g. OFAC's attr_program: ['CUBA']) break pandas
    .duplicated()/.nunique() hashing — stringify them for validation purposes."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def load_and_flatten(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    json_cols = [c for c in CANONICAL_JSON_COLS if c in df.columns]
    if not json_cols:
        return df  # not canonical-schema (e.g. procurement-options, spr schedules)

    flat = df.drop(columns=json_cols)
    for col in json_cols:
        parsed = df[col].apply(_safe_parse)
        if col == "attributes":
            attrs_df = pd.json_normalize(parsed).add_prefix("attr_")
            attrs_df = attrs_df.map(_make_hashable)
            flat = pd.concat([flat.reset_index(drop=True), attrs_df.reset_index(drop=True)], axis=1)
        else:
            flat[f"{col}_present"] = parsed.notna() if hasattr(parsed, "notna") else parsed.apply(lambda v: v is not None)

    # Columns that are 100% null aren't "missing data" — they're fields structurally
    # inapplicable to this entity type (e.g. lat/lon for a sanctioned person, not a place).
    # Dropping them keeps the missing-value check meaningful (genuine partial-missingness)
    # instead of penalizing every dataset for its canonical schema's optional columns.
    always_empty = [c for c in flat.columns if flat[c].isnull().all()]
    if always_empty:
        print(f"  (excluding {len(always_empty)} structurally-inapplicable columns from validation: {always_empty})")
        flat = flat.drop(columns=always_empty)
    return flat


async def main() -> None:
    host = settings.POSTGRES_HOST if settings.POSTGRES_HOST != "postgres" else "localhost"
    pool = await asyncpg.create_pool(
        host=host, port=settings.POSTGRES_PORT, user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD, database=settings.POSTGRES_DB,
        min_size=1, max_size=2,
    )

    validator = DatasetValidationPipeline()
    for name, fn in full_validators():
        validator.add_validator(name, fn)
    quality_gen = QualityReportGenerator()

    summary_rows = []

    for name, (path, version) in DATASETS.items():
        if not path.exists():
            print(f"[SKIP] {name}: file not found at {path}")
            continue

        df = load_and_flatten(path)
        print(f"\n=== {name} v{version} ({len(df)} rows, {len(df.columns)} cols after flattening) ===")

        val_result = await validator.validate(df, name, version)
        for check in val_result["results"]:
            status = "PASS" if check["passed"] else "FAIL"
            print(f"  [{status}] {check['validation_type']}: {check['message']}")
            await pool.execute(
                """INSERT INTO ml.dataset_validations
                   (dataset_name, dataset_version, validation_type, status, score, passed, details)
                   VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)""",
                name, version, check["validation_type"],
                "passed" if check["passed"] else "failed",
                1.0 if check["passed"] else 0.0, check["passed"],
                json.dumps(check["details"]),
            )

        report = quality_gen.generate(df, name, version)
        print(f"  overall quality score: {report.overall_score:.3f}  "
              f"(completeness={report.completeness:.3f} validity={report.validity:.3f} "
              f"uniqueness={report.uniqueness:.3f})")
        for warning in report.warnings:
            print(f"  WARNING: {warning}")

        for col in df.columns:
            missing = int(df[col].isnull().sum())
            unique = int(df[col].nunique(dropna=True))
            await pool.execute(
                """INSERT INTO ml.dataset_profiles
                   (dataset_name, dataset_version, column_name, dtype, missing_count,
                    missing_rate, unique_count, cardinality, profile_json)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                   ON CONFLICT (dataset_name, dataset_version, column_name)
                   DO UPDATE SET missing_count = EXCLUDED.missing_count,
                       missing_rate = EXCLUDED.missing_rate,
                       unique_count = EXCLUDED.unique_count,
                       cardinality = EXCLUDED.cardinality,
                       profile_json = EXCLUDED.profile_json,
                       created_at = now()""",
                name, version, col, str(df[col].dtype), missing,
                round(missing / len(df), 6) if len(df) else 0.0,
                unique, round(unique / len(df), 6) if len(df) else 0.0,
                json.dumps({}),
            )

        summary_rows.append({
            "dataset": name, "rows": len(df), "columns": len(df.columns),
            "quality_score": report.overall_score,
            "checks_passed": val_result["passed"], "checks_total": val_result["total_checks"],
        })

    await pool.close()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    summary_df = pd.DataFrame(summary_rows).sort_values("quality_score")
    print(summary_df.to_string(index=False))
    print(f"\ndatasets validated: {len(summary_df)}")
    print(f"mean quality score: {summary_df['quality_score'].mean():.3f}")
    failing = summary_df[summary_df["checks_passed"] < summary_df["checks_total"]]
    if len(failing):
        print(f"\ndatasets with at least one failed check: {len(failing)}")
        print(failing.to_string(index=False))


if __name__ == "__main__":
    asyncio.run(main())
