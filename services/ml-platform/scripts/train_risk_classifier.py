"""Trains a real disruption/escalation-risk classifier on the GDELT events dataset
registered in ml.dataset_catalog (name='gdelt-events'). Label: escalation_flag,
derived from GDELT's own quad_class (material conflict) and Goldstein scale.

Run from services/ml-platform/ with:
    PYTHONPATH="<repo>;<repo>/services/ml-platform" POSTGRES_* env set
    .venv/Scripts/python.exe scripts/train_risk_classifier.py
"""
from __future__ import annotations

import ast
import asyncio
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.trainer import ModelTrainer  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = REPO_ROOT / "datasets" / "processed" / "gdelt-merged" / "gdelt-events-sample.csv"

TOP_N_COUNTRIES = 30


def load_features() -> tuple[pd.DataFrame, pd.Series]:
    """Label (escalation_flag) is GDELT's own coded severity (quad_class=material conflict,
    or goldstein_scale<=-5). Those two fields are EXCLUDED from X — they define the label,
    so including them would let the model just look up its own answer (leakage). The model
    instead predicts escalation from signals that would be observable as a story breaks:
    media volume/spread/tone and the geography involved."""
    df = pd.read_csv(DATA_PATH)
    attrs = df["attributes"].apply(ast.literal_eval)

    quad_class = attrs.apply(lambda d: d.get("quad_class"))
    goldstein_scale = attrs.apply(lambda d: d.get("goldstein_scale"))
    label = ((quad_class == 4) | (goldstein_scale <= -5)).astype(int)

    feat = pd.DataFrame({
        "avg_tone": attrs.apply(lambda d: d.get("avg_tone")),
        "num_mentions": attrs.apply(lambda d: d.get("num_mentions")),
        "num_sources": attrs.apply(lambda d: d.get("num_sources")),
        "num_articles": attrs.apply(lambda d: d.get("num_articles")),
        "is_root_event": attrs.apply(lambda d: d.get("is_root_event")),
        "actor1_country": attrs.apply(lambda d: d.get("actor1_country") or "NONE"),
        "actor2_country": attrs.apply(lambda d: d.get("actor2_country") or "NONE"),
        "action_geo_country": attrs.apply(lambda d: d.get("action_geo_country") or "NONE"),
    })

    for col in ["actor1_country", "actor2_country", "action_geo_country"]:
        top = feat[col].value_counts().nlargest(TOP_N_COUNTRIES).index
        feat[col] = feat[col].where(feat[col].isin(top), other="OTHER")
        dummies = pd.get_dummies(feat[col], prefix=col, dtype=int)
        feat = pd.concat([feat.drop(columns=[col]), dummies], axis=1)

    feat = feat.apply(pd.to_numeric, errors="coerce").fillna(0)
    return feat, label


def deterministic_split(X: pd.DataFrame, y: pd.Series, seed: int = 42):
    rng = np.random.RandomState(seed)
    idx = rng.permutation(len(X))
    n_train = int(len(X) * 0.8)
    n_val = int(len(X) * 0.1)
    train_idx, val_idx, test_idx = idx[:n_train], idx[n_train:n_train + n_val], idx[n_train + n_val:]
    return (
        X.iloc[train_idx], y.iloc[train_idx],
        X.iloc[val_idx], y.iloc[val_idx],
        X.iloc[test_idx], y.iloc[test_idx],
    )


async def main() -> None:
    print(f"loading features from {DATA_PATH} ...")
    X, y = load_features()
    print(f"rows={len(X)} features={X.shape[1]} positive_rate={y.mean():.4f}")

    X_train, y_train, X_val, y_val, X_test, y_test = deterministic_split(X, y)
    print(f"train={len(X_train)} val={len(X_val)} test={len(X_test)}")

    trainer = ModelTrainer(model_type="xgboost")
    result = await trainer.train(
        model_name="gdelt-disruption-risk-classifier",
        X_train=X_train, y_train=y_train,
        X_val=X_val, y_val=y_val,
        dataset_version=1,
        feature_version=1,
    )
    print("\ntraining complete:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # persist the exact feature column order next to the artifact so serving
    # endpoints can rebuild the vector without re-deriving it from data
    import json
    artifact_dir = Path("data/artifacts") / "gdelt-disruption-risk-classifier" / "v1"
    (artifact_dir / "feature_names.json").write_text(json.dumps(list(X.columns)))
    print(f"feature names saved -> {artifact_dir / 'feature_names.json'} ({X.shape[1]} features)")


if __name__ == "__main__":
    asyncio.run(main())
