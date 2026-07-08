from datetime import datetime
from typing import Any


class MarkdownReportBuilder:
    def __init__(self):
        self._lines: list[str] = []

    def add_header(self, level: int, text: str):
        self._lines.append(f"{'#' * level} {text}\n")

    def add_text(self, text: str):
        self._lines.append(f"{text}\n")

    def add_code_block(self, code: str, language: str = ""):
        self._lines.append(f"```{language}\n{code}\n```\n")

    def add_table(self, headers: list[str], rows: list[list]):
        header_row = "| " + " | ".join(headers) + " |"
        sep_row = "| " + " | ".join("---" for _ in headers) + " |"
        self._lines.append(header_row + "\n" + sep_row + "\n")
        for row in rows:
            formatted = [str(c) if c is not None else "" for c in row]
            self._lines.append("| " + " | ".join(formatted) + " |\n")

    def add_metrics_table(self, metrics: dict):
        headers = ["Metric", "Value"]
        rows = [[k, f"{v:.4f}" if isinstance(v, float) else str(v)] for k, v in metrics.items()]
        self.add_table(headers, rows)

    def add_section(self, title: str, content: str):
        self.add_header(2, title)
        self.add_text(content)

    def add_confusion_matrix(self, cm: list[list], labels: list[str]):
        self.add_header(3, "Confusion Matrix")
        headers = [""] + labels
        rows = [[labels[i]] + [str(cm[i][j]) for j in range(len(cm[i]))] for i in range(len(cm))]
        self.add_table(headers, rows)

    def add_feature_importance(self, importance: dict, top_n: int = 20):
        self.add_header(3, f"Feature Importance (top {top_n})")
        sorted_features = sorted(importance.items(), key=lambda x: abs(x[1]), reverse=True)[:top_n]
        headers = ["Feature", "Importance"]
        rows = [[name, f"{val:.6f}"] for name, val in sorted_features]
        self.add_table(headers, rows)

    def add_separator(self):
        self._lines.append("---\n")

    def build(self) -> str:
        return "".join(self._lines)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.build())


def build_experiment_report(experiment_result: dict) -> str:
    builder = MarkdownReportBuilder()
    name = experiment_result.get("experiment_name", experiment_result.get("name", "Experiment Report"))
    builder.add_header(1, name)
    metadata = []
    if "created_at" in experiment_result:
        metadata.append(f"**Date:** {experiment_result['created_at']}")
    if "git_commit" in experiment_result:
        metadata.append(f"**Git Commit:** `{experiment_result['git_commit']}`")
    if "author" in experiment_result:
        metadata.append(f"**Author:** {experiment_result['author']}")
    if metadata:
        builder.add_text(" | ".join(metadata))
        builder.add_separator()
    config = experiment_result.get("config", experiment_result.get("params", {}))
    if config:
        builder.add_header(2, "Configuration")
        builder.add_header(3, "Model")
        model_info = config.get("model", config)
        if isinstance(model_info, dict):
            model_rows = [["Type", model_info.get("type", "N/A")]]
            for k, v in model_info.get("parameters", {}).items():
                model_rows.append([k, str(v)])
            builder.add_table(["Parameter", "Value"], model_rows)
        builder.add_header(3, "Dataset")
        dataset_info = config.get("dataset", {})
        if dataset_info:
            ds_rows = []
            for k, v in dataset_info.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        ds_rows.append([f"{k}.{sk}", str(sv)])
                else:
                    ds_rows.append([k, str(v)])
            builder.add_table(["Parameter", "Value"], ds_rows)
        builder.add_separator()
    metrics = experiment_result.get("metrics", {})
    if metrics:
        builder.add_header(2, "Metrics")
        primary = {k: v for k, v in metrics.items() if k in ["accuracy", "f1", "precision", "recall", "roc_auc", "mae", "mse", "rmse", "r2", "mape"]}
        if primary:
            builder.add_header(3, "Primary Metrics")
            builder.add_metrics_table(primary)
        if "secondary_metrics" in experiment_result:
            builder.add_header(3, "Secondary Metrics")
            builder.add_metrics_table(experiment_result["secondary_metrics"])
        builder.add_separator()
    cv_results = experiment_result.get("cross_validation", experiment_result.get("cv_results", []))
    if cv_results:
        builder.add_header(2, "Cross-Validation Results")
        if isinstance(cv_results, list) and all(isinstance(r, dict) for r in cv_results):
            keys = list(cv_results[0].keys()) if cv_results else []
            rows = [[str(r.get(k, "")) for k in keys] for r in cv_results]
            builder.add_table(keys, rows)
        builder.add_separator()
    feature_importance = experiment_result.get("feature_importance", {})
    if feature_importance:
        builder.add_feature_importance(feature_importance)
        builder.add_separator()
    cm = experiment_result.get("confusion_matrix", experiment_result.get("cm"))
    cm_labels = experiment_result.get("class_labels", experiment_result.get("labels", []))
    if cm and cm_labels:
        builder.add_confusion_matrix(cm, cm_labels)
        builder.add_separator()
    builder.add_header(2, "Training Details")
    details_rows = []
    if "training_duration_seconds" in experiment_result:
        details_rows.append(["Duration (s)", f"{experiment_result['training_duration_seconds']:.2f}"])
    if "inference_latency_ms" in experiment_result:
        details_rows.append(["Inference Latency (ms)", f"{experiment_result['inference_latency_ms']:.2f}"])
    if "memory_mb" in experiment_result:
        details_rows.append(["Memory (MB)", f"{experiment_result['memory_mb']:.2f}"])
    if "model_size_kb" in experiment_result:
        details_rows.append(["Model Size (KB)", f"{experiment_result['model_size_kb']:.2f}"])
    if details_rows:
        builder.add_table(["Property", "Value"], details_rows)
        builder.add_separator()
    recommendations = experiment_result.get("recommendations", [])
    if recommendations:
        builder.add_header(2, "Recommendations")
        for rec in recommendations:
            builder.add_text(f"- {rec}")
    else:
        metrics_vals = [v for v in metrics.values() if isinstance(v, (int, float))]
        if metrics_vals:
            best = max(metrics_vals)
            builder.add_header(2, "Summary")
            builder.add_text(f"Best metric value: {best:.4f}. Review results and consider hyperparameter tuning for further improvement.")
    return builder.build()
