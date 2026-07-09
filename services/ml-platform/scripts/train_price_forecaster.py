"""Trains the fuel-price forecaster for the Disruption Scenario Modeller.

Data: WFP-style monthly fuel prices (2025-01 .. 2026-05) across ~372 markets,
already parsed into the lake by the CommodityPriceParser (global-fuel-prices).

Task: predict NEXT month's price change (%) per (market, fuel) from lagged
price dynamics. Percent change is used (not raw price) because markets quote
in different local currencies.

Split is BY TIME (no shuffling): train <= 2025-10, val = 2025-11..2026-01,
test = 2026-02..2026-04 targets. This is an honest forecasting protocol —
the model never sees the future.

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/train_price_forecaster.py
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
PRICE_FILES = [
    REPO_ROOT / "datasets" / "processed" / "commodity-prices" / "2025" / "commodity-prices.csv",
    REPO_ROOT / "datasets" / "processed" / "commodity-prices" / "2026" / "commodity-prices.csv",
]

TRAIN_END = "2025-10-01"
VAL_END = "2026-01-01"


def load_panel() -> pd.DataFrame:
    frames = []
    for p in PRICE_FILES:
        df = pd.read_csv(p)
        attrs = df["attributes"].apply(ast.literal_eval)
        frames.append(pd.DataFrame({
            "date": pd.to_datetime(df["timestamp"]),
            "market": df["location_name"],
            "fuel": df["entity_name"],
            "country": attrs.apply(lambda d: d.get("country_code")),
            "price": attrs.apply(lambda d: d.get("price")),
            "trust": attrs.apply(lambda d: d.get("data_trust_score")),
        }))
    panel = pd.concat(frames).dropna(subset=["price"])
    panel = panel.sort_values(["market", "fuel", "date"]).reset_index(drop=True)
    return panel


def build_features(panel: pd.DataFrame) -> pd.DataFrame:
    g = panel.groupby(["market", "fuel"], group_keys=False)

    def per_series(s: pd.DataFrame) -> pd.DataFrame:
        s = s.copy()
        s["ret_1m"] = s["price"].pct_change(1)
        s["ret_2m"] = s["price"].pct_change(2)
        s["ret_3m"] = s["price"].pct_change(3)
        s["vol_3m"] = s["ret_1m"].rolling(3).std()
        s["target_next_ret"] = s["ret_1m"].shift(-1)
        return s

    feat = g.apply(per_series)
    feat["month"] = feat["date"].dt.month
    feat = feat.dropna(subset=["ret_1m", "ret_2m", "ret_3m", "target_next_ret"])
    # clip extreme moves (parallel-market hyperinflation outliers) to stabilise training
    for c in ["ret_1m", "ret_2m", "ret_3m", "target_next_ret"]:
        feat[c] = feat[c].clip(-0.5, 0.5)
    feat["vol_3m"] = feat["vol_3m"].fillna(0).clip(0, 0.5)
    fuel_dummies = pd.get_dummies(feat["fuel"], prefix="fuel", dtype=int)
    return pd.concat([feat.reset_index(drop=True), fuel_dummies.reset_index(drop=True)], axis=1)


async def main() -> None:
    panel = load_panel()
    print(f"panel rows: {len(panel)} | markets: {panel['market'].nunique()} "
          f"| span: {panel['date'].min().date()} -> {panel['date'].max().date()}")

    feat = build_features(panel)
    feature_cols = ["ret_1m", "ret_2m", "ret_3m", "vol_3m", "month"] + \
        [c for c in feat.columns if c.startswith("fuel_") and c != "fuel"]

    train = feat[feat["date"] <= TRAIN_END]
    val = feat[(feat["date"] > TRAIN_END) & (feat["date"] <= VAL_END)]
    test = feat[feat["date"] > VAL_END]
    print(f"rows: train={len(train)} val={len(val)} test={len(test)}")

    trainer = ModelTrainer(
        model_type="xgboost_regressor", task="regression",
        parameters={
            "max_depth": 3, "n_estimators": 300, "learning_rate": 0.05,
            "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 20,
            "reg_lambda": 5.0,
        },
    )
    result = await trainer.train(
        model_name="fuel-price-forecaster",
        X_train=train[feature_cols], y_train=train["target_next_ret"],
        X_val=val[feature_cols], y_val=val["target_next_ret"],
        dataset_version=1, feature_version=1,
    )
    print("\ntraining complete:")
    for k in ("model_name", "model_version", "stage", "mlflow_run_id"):
        print(f"  {k}: {result[k]}")
    print(f"  metrics: {result['metrics']}")

    # honest test evaluation vs naive baselines
    from training.models import REGRESSION_MODEL_REGISTRY
    model = REGRESSION_MODEL_REGISTRY["xgboost_regressor"].load(
        str(Path("data/artifacts/fuel-price-forecaster/v1/model.joblib"))
    )
    preds = model.predict(test[feature_cols])
    y = test["target_next_ret"].values
    mae_model = float(np.mean(np.abs(preds - y)))
    mae_zero = float(np.mean(np.abs(y)))                     # naive: "no change"
    mae_persist = float(np.mean(np.abs(test["ret_1m"].values - y)))  # naive: repeat last move
    print(f"\nheld-out test ({test['date'].min().date()} -> {test['date'].max().date()}):")
    print(f"  model MAE:            {mae_model:.4f}")
    print(f"  naive no-change MAE:  {mae_zero:.4f}  (model better by {(1 - mae_model / mae_zero):.1%})")
    print(f"  naive persistence MAE:{mae_persist:.4f}  (model better by {(1 - mae_model / mae_persist):.1%})")


if __name__ == "__main__":
    asyncio.run(main())
