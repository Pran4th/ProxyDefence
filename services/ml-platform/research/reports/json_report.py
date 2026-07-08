import json
from datetime import datetime
from typing import Any


class JSONReportBuilder:
    def build(self, experiment_result: dict) -> str:
        return build_json_report(experiment_result)

    def save(self, path: str, data: dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)


def build_json_report(experiment_result: dict) -> str:
    report = {
        "report_type": "experiment_report",
        "generated_at": datetime.now().isoformat(),
        "experiment": {
            "name": experiment_result.get("experiment_name", experiment_result.get("name", "unknown")),
            "type": experiment_result.get("experiment_type", experiment_result.get("type", "classification")),
            "author": experiment_result.get("author", "system"),
            "status": experiment_result.get("status", "completed"),
            "git_commit": experiment_result.get("git_commit"),
            "created_at": experiment_result.get("created_at", datetime.now().isoformat()),
        },
        "config": experiment_result.get("config", experiment_result.get("params", {})),
        "metrics": experiment_result.get("metrics", {}),
        "secondary_metrics": experiment_result.get("secondary_metrics", {}),
        "cross_validation": experiment_result.get("cross_validation", experiment_result.get("cv_results", [])),
        "feature_importance": experiment_result.get("feature_importance", {}),
        "confusion_matrix": experiment_result.get("confusion_matrix", experiment_result.get("cm")),
        "class_labels": experiment_result.get("class_labels", experiment_result.get("labels", [])),
        "training_details": {
            "duration_seconds": experiment_result.get("training_duration_seconds"),
            "inference_latency_ms": experiment_result.get("inference_latency_ms"),
            "memory_mb": experiment_result.get("memory_mb"),
            "model_size_kb": experiment_result.get("model_size_kb"),
        },
        "recommendations": experiment_result.get("recommendations", []),
        "dataset": experiment_result.get("dataset", {}),
    }
    report = {k: v for k, v in report.items() if v is not None and v != {} and v != []}
    return json.dumps(report, indent=2, default=str)
