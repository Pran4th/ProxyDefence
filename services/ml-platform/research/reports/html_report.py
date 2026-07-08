import json
from datetime import datetime
from typing import Any

_CSS = """
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #e0e0e0; background: #1a1a2e; max-width: 960px; margin: 0 auto; padding: 2rem; }
h1 { color: #00d4aa; border-bottom: 2px solid #00d4aa; padding-bottom: 0.5rem; margin-bottom: 1.5rem; font-size: 1.8rem; }
h2 { color: #64ffda; margin-top: 2rem; margin-bottom: 1rem; font-size: 1.4rem; }
h3 { color: #a8e6cf; margin-top: 1.5rem; margin-bottom: 0.75rem; font-size: 1.15rem; }
p { margin-bottom: 1rem; }
.metadata { color: #8892b0; font-size: 0.9rem; margin-bottom: 1.5rem; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0 1.5rem; background: #16213e; border-radius: 8px; overflow: hidden; }
th, td { padding: 0.6rem 1rem; text-align: left; border-bottom: 1px solid #0f3460; }
th { background: #0f3460; color: #64ffda; font-weight: 600; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.05em; }
tr:hover { background: #1a2744; }
code { background: #0f3460; padding: 0.15rem 0.4rem; border-radius: 4px; font-family: 'Fira Code', 'Consolas', monospace; font-size: 0.9em; color: #ffd700; }
.section { margin: 1.5rem 0; }
.badge { display: inline-block; background: #00d4aa; color: #1a1a2e; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
hr { border: none; border-top: 1px solid #0f3460; margin: 2rem 0; }
</style>
"""


class HTMLReportBuilder:
    def build(self, experiment_result: dict) -> str:
        return build_html_report(experiment_result)

    def save(self, path: str, data: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)


def _build_table(headers: list[str], rows: list[list[str]]) -> str:
    parts = ["<table><thead><tr>"]
    for h in headers:
        parts.append(f"<th>{h}</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td>{cell}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _build_metrics_table(metrics: dict) -> str:
    rows = [[k, f"{v:.4f}" if isinstance(v, float) else str(v)] for k, v in metrics.items()]
    return _build_table(["Metric", "Value"], rows)


def build_html_report(experiment_result: dict) -> str:
    name = experiment_result.get("experiment_name", experiment_result.get("name", "Experiment Report"))
    parts = ["<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>",
             f"<title>{name}</title>", _CSS, "</head><body>"]
    parts.append(f"<h1>{name}</h1>")
    meta_parts_list = []
    if "created_at" in experiment_result:
        meta_parts_list.append(f"<strong>Date:</strong> {experiment_result['created_at']}")
    if "git_commit" in experiment_result:
        meta_parts_list.append(f"<strong>Git Commit:</strong> <code>{experiment_result['git_commit']}</code>")
    if "author" in experiment_result:
        meta_parts_list.append(f"<strong>Author:</strong> {experiment_result['author']}")
    if meta_parts_list:
        parts.append(f"<p class='metadata'>{' | '.join(meta_parts_list)}</p>")
    parts.append("<hr>")
    config = experiment_result.get("config", experiment_result.get("params", {}))
    if config:
        parts.append("<div class='section'><h2>Configuration</h2>")
        model_info = config.get("model", config)
        if isinstance(model_info, dict):
            parts.append("<h3>Model</h3>")
            model_rows = [["<strong>Type</strong>", model_info.get("type", "N/A")]]
            for k, v in model_info.get("parameters", {}).items():
                model_rows.append([k, str(v)])
            parts.append(_build_table(["Parameter", "Value"], model_rows))
        dataset_info = config.get("dataset", {})
        if dataset_info:
            parts.append("<h3>Dataset</h3>")
            ds_rows = []
            for k, v in dataset_info.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        ds_rows.append([f"{k}.{sk}", str(sv)])
                else:
                    ds_rows.append([k, str(v)])
            parts.append(_build_table(["Parameter", "Value"], ds_rows))
        parts.append("</div><hr>")
    metrics = experiment_result.get("metrics", {})
    if metrics:
        parts.append("<div class='section'><h2>Metrics</h2>")
        primary = {k: v for k, v in metrics.items() if k in ["accuracy", "f1", "precision", "recall", "roc_auc", "mae", "mse", "rmse", "r2", "mape"]}
        if primary:
            parts.append("<h3>Primary Metrics</h3>")
            parts.append(_build_metrics_table(primary))
        if "secondary_metrics" in experiment_result:
            parts.append("<h3>Secondary Metrics</h3>")
            parts.append(_build_metrics_table(experiment_result["secondary_metrics"]))
        parts.append("</div><hr>")
    cv_results = experiment_result.get("cross_validation", experiment_result.get("cv_results", []))
    if cv_results:
        parts.append("<div class='section'><h2>Cross-Validation Results</h2>")
        if isinstance(cv_results, list) and all(isinstance(r, dict) for r in cv_results):
            keys = list(cv_results[0].keys()) if cv_results else []
            rows = [[str(r.get(k, "")) for k in keys] for r in cv_results]
            parts.append(_build_table(keys, rows))
        parts.append("</div><hr>")
    feature_importance = experiment_result.get("feature_importance", {})
    if feature_importance:
        parts.append("<div class='section'><h2>Feature Importance</h2>")
        sorted_features = sorted(feature_importance.items(), key=lambda x: abs(x[1]), reverse=True)[:20]
        parts.append(_build_table(["Feature", "Importance"], [[n, f"{v:.6f}"] for n, v in sorted_features]))
        parts.append("</div><hr>")
    cm = experiment_result.get("confusion_matrix", experiment_result.get("cm"))
    cm_labels = experiment_result.get("class_labels", experiment_result.get("labels", []))
    if cm and cm_labels:
        parts.append("<div class='section'><h2>Confusion Matrix</h2>")
        headers = [""] + cm_labels
        rows = [[cm_labels[i]] + [str(cm[i][j]) for j in range(len(cm[i]))] for i in range(len(cm))]
        parts.append(_build_table(headers, rows))
        parts.append("</div><hr>")
    parts.append("<div class='section'><h2>Training Details</h2>")
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
        parts.append(_build_table(["Property", "Value"], details_rows))
    parts.append("</div><hr>")
    recommendations = experiment_result.get("recommendations", [])
    if recommendations:
        parts.append("<div class='section'><h2>Recommendations</h2><ul>")
        for rec in recommendations:
            parts.append(f"<li>{rec}</li>")
        parts.append("</ul></div>")
    else:
        parts.append("<div class='section'><h2>Summary</h2>")
        parts.append("<p>Review results and consider hyperparameter tuning for further improvement.</p></div>")
    parts.append("</body></html>")
    return "".join(parts)
