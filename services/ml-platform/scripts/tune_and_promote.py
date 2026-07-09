"""One Optuna tuning pass per model, reusing each training script's existing
feature-loading logic (no duplication). Retrains with the best-found
hyperparameters, compares against the current production version's held-out
metric, and promotes the winner / archives the loser.

Run from services/ml-platform/ with POSTGRES_* env + MLFLOW_ALLOW_FILE_STORE=true set:
    .venv/Scripts/python.exe scripts/tune_and_promote.py [model_name ...]
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np
import optuna

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402
from backend.shared.settings import settings  # noqa: E402
from training.trainer import ModelTrainer  # noqa: E402

optuna.logging.set_verbosity(optuna.logging.WARNING)

N_TRIALS = 20
SEED = 42


def _xgb_search_space(trial: optuna.Trial) -> dict:
    return {
        "max_depth": trial.suggest_int("max_depth", 2, 6),
        "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 30),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 20.0, log=True),
    }


async def tune_risk_classifier() -> dict:
    from scripts.train_risk_classifier import load_features, deterministic_split

    X, y = load_features()
    X_train, y_train, X_val, y_val, _, _ = deterministic_split(X, y)

    def objective(trial: optuna.Trial) -> float:
        params = _xgb_search_space(trial)
        params["eval_metric"] = "logloss"
        from training.models import XGBoostWrapper
        model = XGBoostWrapper(random_state=SEED, **params)
        model.fit(X_train, y_train)
        from evaluation.classification import evaluate_classification
        proba = model.predict_proba(X_val)
        preds = model.predict(X_val)
        metrics = evaluate_classification(y_val, preds, proba)
        return metrics.get("roc_auc", 0.0) or 0.0

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=False)
    print(f"  best val_roc_auc from tuning: {study.best_value:.4f} (params: {study.best_params})")

    trainer = ModelTrainer(model_type="xgboost", parameters=study.best_params)
    result = await trainer.train(
        model_name="gdelt-disruption-risk-classifier",
        X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val,
        dataset_version=1, feature_version=1,
    )
    return {"result": result, "compare_metric": "val_roc_auc"}


async def tune_procurement_ranker() -> dict:
    from scripts.train_procurement_ranker import load_split

    train, val, _, feature_cols = load_split()

    def objective(trial: optuna.Trial) -> float:
        params = _xgb_search_space(trial)
        from training.models import XGBoostRegressorWrapper
        model = XGBoostRegressorWrapper(random_state=SEED, **params)
        model.fit(train[feature_cols], train["outcome_score"])
        preds = model.predict(val[feature_cols])
        from evaluation.regression import evaluate_regression
        return evaluate_regression(val["outcome_score"], preds).get("r2", -1e9)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=False)
    print(f"  best val_r2 from tuning: {study.best_value:.4f} (params: {study.best_params})")

    trainer = ModelTrainer(model_type="xgboost_regressor", task="regression", parameters=study.best_params)
    result = await trainer.train(
        model_name="procurement-option-ranker",
        X_train=train[feature_cols], y_train=train["outcome_score"],
        X_val=val[feature_cols], y_val=val["outcome_score"],
        dataset_version=1, feature_version=1,
    )
    return {"result": result, "compare_metric": "val_r2"}


async def tune_price_forecaster() -> dict:
    from scripts.train_price_forecaster import load_panel, build_features, TRAIN_END, VAL_END

    panel = load_panel()
    feat = build_features(panel)
    feature_cols = ["ret_1m", "ret_2m", "ret_3m", "vol_3m", "month"] + \
        [c for c in feat.columns if c.startswith("fuel_") and c != "fuel"]
    train = feat[feat["date"] <= TRAIN_END]
    val = feat[(feat["date"] > TRAIN_END) & (feat["date"] <= VAL_END)]

    def objective(trial: optuna.Trial) -> float:
        params = _xgb_search_space(trial)
        from training.models import XGBoostRegressorWrapper
        model = XGBoostRegressorWrapper(random_state=SEED, **params)
        model.fit(train[feature_cols], train["target_next_ret"])
        preds = model.predict(val[feature_cols])
        from evaluation.regression import evaluate_regression
        return evaluate_regression(val["target_next_ret"], preds).get("r2", -1e9)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=False)
    print(f"  best val_r2 from tuning: {study.best_value:.4f} (params: {study.best_params})")

    trainer = ModelTrainer(model_type="xgboost_regressor", task="regression", parameters=study.best_params)
    result = await trainer.train(
        model_name="fuel-price-forecaster",
        X_train=train[feature_cols], y_train=train["target_next_ret"],
        X_val=val[feature_cols], y_val=val["target_next_ret"],
        dataset_version=1, feature_version=1,
    )
    return {"result": result, "compare_metric": "val_r2"}


async def tune_brent_shock() -> dict:
    from scripts.train_brent_shock_model import load_series, build_features, FEATURES, TRAIN_END, VAL_END

    s = load_series()
    feat = build_features(s)
    train = feat[feat["date"] <= TRAIN_END]
    val = feat[(feat["date"] > TRAIN_END) & (feat["date"] <= VAL_END)]

    def objective(trial: optuna.Trial) -> float:
        params = _xgb_search_space(trial)
        from training.models import XGBoostRegressorWrapper
        model = XGBoostRegressorWrapper(random_state=SEED, **params)
        model.fit(train[FEATURES], train["target_fwd_vol"])
        preds = model.predict(val[FEATURES])
        from evaluation.regression import evaluate_regression
        return evaluate_regression(val["target_fwd_vol"], preds).get("r2", -1e9)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=False)
    print(f"  best val_r2 from tuning: {study.best_value:.4f} (params: {study.best_params})")

    trainer = ModelTrainer(model_type="xgboost_regressor", task="regression", parameters=study.best_params)
    result = await trainer.train(
        model_name="brent-shock-forecaster",
        X_train=train[FEATURES], y_train=train["target_fwd_vol"],
        X_val=val[FEATURES], y_val=val["target_fwd_vol"],
        dataset_version=1, feature_version=1,
    )
    return {"result": result, "compare_metric": "val_r2"}


TUNERS = {
    "gdelt-disruption-risk-classifier": tune_risk_classifier,
    "procurement-option-ranker": tune_procurement_ranker,
    "fuel-price-forecaster": tune_price_forecaster,
    "brent-shock-forecaster": tune_brent_shock,
}


async def promote_best(pool: asyncpg.Pool, model_name: str, new_version: int, compare_metric: str) -> None:
    rows = await pool.fetch(
        "SELECT version, metrics, stage FROM ml.model_versions WHERE name = $1 ORDER BY version",
        model_name,
    )
    import json as _json
    scored = []
    for r in rows:
        metrics = r["metrics"]
        metrics = _json.loads(metrics) if isinstance(metrics, str) else (metrics or {})
        score = metrics.get(compare_metric)
        if score is not None:
            scored.append((r["version"], float(score), r["stage"]))

    if not scored:
        print(f"  [promote] no comparable versions found for {model_name}")
        return

    best_version, best_score, _ = max(scored, key=lambda t: t[1])
    print(f"  [promote] {model_name}: best={compare_metric}={best_score:.4f} is v{best_version} "
          f"(candidates: {[(v, round(s,4)) for v,s,_ in scored]})")

    await pool.execute(
        "UPDATE ml.model_versions SET stage = 'production' WHERE name = $1 AND version = $2",
        model_name, best_version,
    )
    await pool.execute(
        "UPDATE ml.model_versions SET stage = 'archived' "
        "WHERE name = $1 AND version != $2 AND stage = 'production'",
        model_name, best_version,
    )


async def main() -> None:
    targets = sys.argv[1:] or list(TUNERS.keys())
    host = settings.POSTGRES_HOST if settings.POSTGRES_HOST != "postgres" else "localhost"
    pool = await asyncpg.create_pool(
        host=host, port=settings.POSTGRES_PORT, user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD, database=settings.POSTGRES_DB,
        min_size=1, max_size=2,
    )

    for name in targets:
        print(f"\n=== tuning {name} ({N_TRIALS} trials) ===")
        tuner = TUNERS[name]
        outcome = await tuner()
        result = outcome["result"]
        print(f"  new version trained: v{result['model_version']} "
              f"metrics={ {k: v for k, v in result['metrics'].items() if isinstance(v,(int,float))} }")
        await promote_best(pool, name, result["model_version"], outcome["compare_metric"])

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
