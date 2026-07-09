"""Trains the procurement option ranker: an XGBoost regressor that predicts the
expected (risk-adjusted) outcome score of a supplier option. Ranking candidate
suppliers by this prediction = the ML-driven ranking for the Adaptive
Procurement Orchestrator.

Split is BY SCENARIO (run_id), not by row — options from the same scenario share
the market regime, so a row-wise split would leak regime information.

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/train_procurement_ranker.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.trainer import ModelTrainer  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = REPO_ROOT / "datasets" / "processed" / "procurement" / "procurement-options.csv"

FEATURES = [
    "cost_bbl", "lead_time_days", "reliability_score", "on_time_delivery_pct",
    "strategic_value", "country_stability_base", "sanction_count",
    "gdelt_escalation_rate", "port_congestion_index", "brent_anchor",
]
TARGET = "outcome_score"
SEED = 42


def load_split(seed: int = SEED):
    """Returns (train, val, test, feature_cols) split by scenario (run_id) so
    options from the same market regime don't leak across splits."""
    df = pd.read_csv(DATA_PATH)
    df = pd.concat([df, pd.get_dummies(df["supplier_type"], prefix="stype", dtype=int)], axis=1)
    feature_cols = FEATURES + [c for c in df.columns if c.startswith("stype_")]

    rng = np.random.RandomState(seed)
    runs = df["run_id"].unique()
    rng.shuffle(runs)
    n_train = int(len(runs) * 0.8)
    n_val = int(len(runs) * 0.1)
    train_runs, val_runs = set(runs[:n_train]), set(runs[n_train:n_train + n_val])
    test_runs = set(runs[n_train + n_val:])

    train = df[df["run_id"].isin(train_runs)]
    val = df[df["run_id"].isin(val_runs)]
    test = df[df["run_id"].isin(test_runs)]
    return train, val, test, feature_cols


async def main() -> None:
    train, val, test, feature_cols = load_split()
    print(f"rows: train={len(train)} val={len(val)} test={len(test)}")

    trainer = ModelTrainer(
        model_type="xgboost_regressor", task="regression",
        parameters={
            "max_depth": 3, "n_estimators": 250, "learning_rate": 0.05,
            "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 10,
            "reg_lambda": 5.0,
        },
    )
    result = await trainer.train(
        model_name="procurement-option-ranker",
        X_train=train[feature_cols], y_train=train[TARGET],
        X_val=val[feature_cols], y_val=val[TARGET],
        dataset_version=1, feature_version=1,
    )
    print("\ntraining complete:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Ranking sanity check on held-out scenarios: how often does the model's
    # top-ranked supplier match the actual best outcome in that scenario?
    from training.models import REGRESSION_MODEL_REGISTRY
    model = REGRESSION_MODEL_REGISTRY["xgboost_regressor"].load(
        str(Path("data/artifacts/procurement-option-ranker/v1/model.joblib"))
    )
    hits_top1, hits_top3, n = 0, 0, 0
    for run_id, grp in test.groupby("run_id"):
        preds = model.predict(grp[feature_cols])
        pred_order = grp.iloc[np.argsort(-preds)]["supplier_slug"].tolist()
        true_best = grp.iloc[grp[TARGET].values.argmax()]["supplier_slug"]
        hits_top1 += int(pred_order[0] == true_best)
        hits_top3 += int(true_best in pred_order[:3])
        n += 1
    print(f"\nheld-out ranking quality over {n} scenarios:")
    print(f"  top-1 hit rate: {hits_top1 / n:.3f}")
    print(f"  top-3 hit rate: {hits_top3 / n:.3f}")

    sample = test[test["run_id"] == sorted(test["run_id"].unique())[0]].copy()
    sample["predicted"] = model.predict(sample[feature_cols])
    sample = sample.sort_values("predicted", ascending=False)
    print("\nexample ranking (one held-out scenario):")
    print(sample[["supplier_slug", "cost_bbl", "sanction_count",
                  "gdelt_escalation_rate", "predicted", TARGET]].to_string(index=False))


if __name__ == "__main__":
    asyncio.run(main())
