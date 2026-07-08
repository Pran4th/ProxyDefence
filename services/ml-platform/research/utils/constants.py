class ResearchConstants:
    VALID_MODEL_TYPES = [
        "logistic_regression", "decision_tree", "random_forest",
        "xgboost", "lightgbm", "catboost",
    ]

    VALID_DATASET_TYPES = [
        "news_articles", "energy_infrastructure", "knowledge_graph",
        "risk_signals", "commodity_prices", "digital_twin",
        "procurement", "spr", "events", "entity_relationships",
        "graph_embeddings", "hybrid",
    ]

    VALID_EXPERIMENT_STATUSES = ["draft", "running", "completed", "failed", "cancelled"]

    VALID_EXPERIMENT_TYPES = [
        "classification", "regression", "forecasting", "anomaly_detection",
        "ranking", "clustering", "dimensionality_reduction", "graph_learning",
    ]

    VALID_RUN_STATUSES = ["pending", "running", "completed", "failed", "cancelled"]

    CLASSIFICATION_METRICS = ["accuracy", "precision", "recall", "f1", "roc_auc"]
    REGRESSION_METRICS = ["mae", "mse", "rmse", "r2", "mape"]
    FORECASTING_METRICS = ["mae", "mse", "rmse", "mase", "smape"]
    ANOMALY_METRICS = ["precision", "recall", "f1", "auc_pr"]

    DEFAULT_SPLIT_RATIOS = {"train": 0.7, "validation": 0.15, "test": 0.15}

    PRODUCTION_MODEL_STAGES = ["development", "validation", "staging", "production", "archived"]

    QUARTILE_LABELS = {0: "low", 1: "medium", 2: "high", 3: "critical"}
