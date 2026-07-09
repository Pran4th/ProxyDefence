"""Trains a real topic classifier to replace ml_core/topic.py's keyword-counting
heuristic (war/diplomacy/economics/cyber/general — the exact 5 categories
ml_core.classify_topic already emits, so this is a drop-in upgrade, not a
schema change).

LABEL SOURCE (explicit, documented tradeoff — see plan Phase 3 step 1): GDELT's
own GKG theme taxonomy is grouped into the 5 target categories via keyword
matching on theme names (e.g. ARMEDCONFLICT/MILITARY/TERROR -> "war"). This is
a PROXY label, not hand-labeled ground truth for these exact categories.

FEATURES: TF-IDF over words extracted from each article's URL slug
(document_identifier) — e.g. ".../story/8271818/illegal-fireworks-and-rain-
brings-in-2024/" -> "illegal fireworks and rain brings in 2024". This is
genuine headline-adjacent text, independent of the theme tags used for the
label (no circular leakage), and the same kind of short, keyword-dense text
ml_core.classify_topic already receives (article title + summary).

Run from services/ml-platform/ with POSTGRES_* env + MLFLOW_ALLOW_FILE_STORE=true:
    .venv/Scripts/python.exe scripts/train_topic_classifier.py
"""
from __future__ import annotations

import ast
import asyncio
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.trainer import ModelTrainer  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = REPO_ROOT / "datasets" / "processed" / "gdelt-gkg-merged" / "gkg-merged.csv"
SEED = 42
MAX_FEATURES = 400

# Theme-substring -> target category. Matches ml_core/topic.py's 4 categories + "general" fallback.
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("cyber", ["CYBER"]),
    ("war", ["ARMEDCONFLICT", "MILITARY", "TERROR", "KILL", "CRISISLEX_T03_DEAD", "SECURITY_SERVICES", "TAX_WEAPON"]),
    ("diplomacy", ["LEADER", "GENERAL_GOVERNMENT", "TREATY", "SUMMIT", "NEGOTIATION", "PEACEKEEPING", "USPEC_POLITICS", "USPEC_POLICY"]),
    ("economics", ["ECON_", "WB_698_TRADE", "TRADE_DISPUTE", "SANCTION", "WB_696_PUBLIC_SECTOR", "EPU_POLICY"]),
]


def theme_to_category(themes: list[str]) -> str | None:
    for category, substrings in CATEGORY_RULES:
        if any(any(sub in t for sub in substrings) for t in themes):
            return category
    return None  # ambiguous/no signal -> excluded from training (not forced into "general")


def slug_text(url: str) -> str:
    if not isinstance(url, str):
        return ""
    m = re.search(r"/([a-z0-9-]{15,})(?:/|\?|$)", url.lower())
    if not m:
        return ""
    return m.group(1).replace("-", " ")


def load_labeled_text(seed: int = SEED) -> pd.DataFrame:
    """Rows whose themes match none of the 4 keyword-defined categories become
    "general" (not dropped) — otherwise the classifier can structurally never
    predict "general", which is one of ml_core.topic's 5 real output values
    (war/diplomacy/economics/cyber/general). "general" is subsampled to the
    size of the largest matched category so it doesn't dominate the training
    distribution (it would otherwise outnumber all 4 matched categories combined)."""
    df = pd.read_csv(DATA_PATH)
    attrs = df["attributes"].apply(lambda s: ast.literal_eval(s) if isinstance(s, str) else {})
    themes = attrs.apply(lambda a: a.get("themes") or [])
    urls = attrs.apply(lambda a: a.get("document_identifier") or "")

    frame = pd.DataFrame({
        "text": urls.apply(slug_text),
        "category": themes.apply(lambda t: theme_to_category(t) or "general"),
    })
    frame = frame[frame["text"].str.split().str.len() >= 3]

    matched = frame[frame["category"] != "general"]
    general = frame[frame["category"] == "general"]
    cap = matched["category"].value_counts().max() if len(matched) else len(general)
    if len(general) > cap:
        general = general.sample(n=cap, random_state=seed)

    return pd.concat([matched, general], ignore_index=True)


async def main() -> None:
    frame = load_labeled_text()
    print(f"labeled rows: {len(frame)} (from {pd.read_csv(DATA_PATH).shape[0]} raw GKG records)")
    print("category distribution:")
    print(frame["category"].value_counts().to_string())

    rng = np.random.RandomState(SEED)
    idx = rng.permutation(len(frame))
    n_train = int(len(frame) * 0.8)
    n_val = int(len(frame) * 0.1)
    train_idx, val_idx, test_idx = idx[:n_train], idx[n_train:n_train + n_val], idx[n_train + n_val:]

    vectorizer = TfidfVectorizer(max_features=MAX_FEATURES, stop_words="english", ngram_range=(1, 2))
    X_all = vectorizer.fit_transform(frame["text"]).toarray()
    X = pd.DataFrame(X_all, columns=[f"tfidf_{i}" for i in range(X_all.shape[1])])

    categories = sorted(frame["category"].unique())
    cat_to_idx = {c: i for i, c in enumerate(categories)}
    y = frame["category"].map(cat_to_idx)

    X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
    X_val, y_val = X.iloc[val_idx], y.iloc[val_idx]
    X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
    print(f"\nsplit: train={len(X_train)} val={len(X_val)} test={len(X_test)}")
    print(f"categories: {categories}")

    trainer = ModelTrainer(
        model_type="xgboost",
        parameters={"max_depth": 5, "n_estimators": 200, "learning_rate": 0.1, "objective": "multi:softprob"},
    )
    result = await trainer.train(
        model_name="article-topic-classifier",
        X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val,
        dataset_version=1, feature_version=1,
    )
    print("\ntraining complete:")
    for k in ("model_name", "model_version", "stage"):
        print(f"  {k}: {result[k]}")
    print(f"  val_accuracy: {result['metrics'].get('val_accuracy')}")
    print(f"  val_f1_weighted: {result['metrics'].get('val_f1_weighted')}")

    # honest held-out test + naive baseline (predict majority class always)
    from training.models import MODEL_REGISTRY
    model = MODEL_REGISTRY["xgboost"].load(
        str(Path("data/artifacts/article-topic-classifier/v1/model.joblib"))
    )
    test_preds = model.predict(X_test)
    test_acc = float((test_preds == y_test.values).mean())
    majority_class = y_train.value_counts().idxmax()
    naive_acc = float((y_test.values == majority_class).mean())
    print(f"\nheld-out test accuracy: {test_acc:.4f}")
    print(f"naive majority-class baseline ({categories[majority_class]}): {naive_acc:.4f}")
    print(f"model beats naive baseline by: {(test_acc - naive_acc):.4f}")

    # save vectorizer + category map alongside the model artifact, same convention as feature_names.json
    import json
    import joblib
    artifact_dir = Path("data/artifacts/article-topic-classifier/v1")
    joblib.dump(vectorizer, artifact_dir / "tfidf_vectorizer.joblib")
    (artifact_dir / "categories.json").write_text(json.dumps(categories))
    print(f"\nvectorizer + categories saved -> {artifact_dir}")


if __name__ == "__main__":
    asyncio.run(main())
