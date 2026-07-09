"""Trains the Brent price-shock (volatility) forecaster for the Disruption
Scenario Modeller.

Data: FRED DCOILBRENTEU daily Brent spot (1987 -> present, ~10k obs), parsed
into the lake as fred-oil-prices/brent_daily.

Task: predict NEXT-5-trading-day realized volatility (std of daily log
returns) from recent return/volatility dynamics. High predicted vol = price
shock conditions -> feeds scenario stress assumptions.

Split BY TIME: train <= 2018, val 2019-2021 (includes COVID shock),
test 2022+ (includes Ukraine invasion + 2025-26 Hormuz stress) — the hardest
possible out-of-sample regime.

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/train_brent_shock_model.py
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
DATA_PATH = REPO_ROOT / "datasets" / "processed" / "fred-oil-prices" / "brent_daily" / "fred-oil-prices.csv"

TRAIN_END = "2018-12-31"
VAL_END = "2021-12-31"
HORIZON = 5  # trading days


def load_series() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    attrs = df["attributes"].apply(ast.literal_eval)
    s = pd.DataFrame({
        "date": pd.to_datetime(df["timestamp"]),
        "price": attrs.apply(lambda d: d.get("value")),
    }).dropna()
    s["price"] = pd.to_numeric(s["price"], errors="coerce")
    s = s.dropna().sort_values("date").reset_index(drop=True)
    return s


def build_features(s: pd.DataFrame) -> pd.DataFrame:
    s = s.copy()
    s["ret"] = np.log(s["price"]).diff()
    s["ret_1"] = s["ret"].shift(1)
    s["ret_5_sum"] = s["ret"].rolling(5).sum()
    s["vol_5"] = s["ret"].rolling(5).std()
    s["vol_21"] = s["ret"].rolling(21).std()
    s["vol_63"] = s["ret"].rolling(63).std()
    s["vol_ratio"] = s["vol_5"] / s["vol_21"]
    s["abs_ret"] = s["ret"].abs()
    s["max_abs_ret_5"] = s["abs_ret"].rolling(5).max()
    s["price_z_63"] = (s["price"] - s["price"].rolling(63).mean()) / s["price"].rolling(63).std()
    # target: realized vol over the NEXT `HORIZON` days
    fwd = s["ret"].shift(-1).rolling(HORIZON).std().shift(-(HORIZON - 1))
    s["target_fwd_vol"] = fwd
    return s.dropna().reset_index(drop=True)


FEATURES = ["ret", "ret_1", "ret_5_sum", "vol_5", "vol_21", "vol_63",
            "vol_ratio", "abs_ret", "max_abs_ret_5", "price_z_63"]


async def main() -> None:
    s = load_series()
    print(f"brent series: {len(s)} obs, {s['date'].min().date()} -> {s['date'].max().date()}")

    feat = build_features(s)
    train = feat[feat["date"] <= TRAIN_END]
    val = feat[(feat["date"] > TRAIN_END) & (feat["date"] <= VAL_END)]
    test = feat[feat["date"] > VAL_END]
    print(f"rows: train={len(train)} val={len(val)} test={len(test)}")

    trainer = ModelTrainer(
        model_type="xgboost_regressor", task="regression",
        parameters={
            "max_depth": 3, "n_estimators": 400, "learning_rate": 0.03,
            "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 30,
            "reg_lambda": 10.0,
        },
    )
    result = await trainer.train(
        model_name="brent-shock-forecaster",
        X_train=train[FEATURES], y_train=train["target_fwd_vol"],
        X_val=val[FEATURES], y_val=val["target_fwd_vol"],
        dataset_version=1, feature_version=1,
    )
    print("\ntraining complete:")
    for k in ("model_name", "model_version", "stage"):
        print(f"  {k}: {result[k]}")
    print(f"  metrics: {result['metrics']}")

    # test-set comparison vs the standard persistence baseline (vol_5 carries forward)
    from training.models import REGRESSION_MODEL_REGISTRY
    model = REGRESSION_MODEL_REGISTRY["xgboost_regressor"].load(
        str(Path("data/artifacts/brent-shock-forecaster/v1/model.joblib"))
    )
    preds = model.predict(test[FEATURES])
    y = test["target_fwd_vol"].values
    mae_model = float(np.mean(np.abs(preds - y)))
    mae_persist = float(np.mean(np.abs(test["vol_5"].values - y)))
    mae_ewma = float(np.mean(np.abs(test["vol_21"].values - y)))
    print(f"\nheld-out test 2022+ ({len(test)} days, includes Ukraine + Hormuz stress):")
    print(f"  model MAE:              {mae_model:.5f}")
    print(f"  persistence (vol_5):    {mae_persist:.5f}  (model better by {(1 - mae_model / mae_persist):.1%})")
    print(f"  slow anchor (vol_21):   {mae_ewma:.5f}  (model better by {(1 - mae_model / mae_ewma):.1%})")

    # example: what does the model say about the most recent days?
    tail = test.tail(3).copy()
    tail["pred_fwd_vol_annualized"] = model.predict(tail[FEATURES]) * np.sqrt(252)
    print("\nlatest signal (annualized forward vol):")
    print(tail[["date", "price", "pred_fwd_vol_annualized"]].to_string(index=False))


if __name__ == "__main__":
    asyncio.run(main())
