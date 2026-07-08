import json
from datetime import datetime
from pathlib import Path
from typing import Any


class EvaluationReporter:
    def __init__(self, output_dir: str = "./data/reports"):
        self._output_dir = Path(output_dir)

    def generate_report(self, metrics: dict[str, Any],
                        model_name: str, model_version: int,
                        dataset_version: int | None = None,
                        feature_version: int | None = None,
                        execution_time: float | None = None,
                        cv_scores: list[float] | None = None,
                        extra: dict[str, Any] | None = None) -> dict[str, Any]:
        report = {
            "report_timestamp": datetime.utcnow().isoformat(),
            "model_name": model_name,
            "model_version": model_version,
            "dataset_version": dataset_version,
            "feature_version": feature_version,
            "execution_time_seconds": execution_time,
            "metrics": metrics,
        }
        if cv_scores:
            report["cross_validation"] = {
                "scores": [round(s, 4) for s in cv_scores],
                "mean": round(float(sum(cv_scores) / len(cv_scores)), 4),
                "std": round(float(__import__("numpy").std(cv_scores)), 4),
            }
        if extra:
            report.update(extra)

        return report

    def format_markdown(self, report: dict[str, Any]) -> str:
        lines = []
        lines.append(f"# Evaluation Report: {report.get('model_name', 'unknown')}")
        lines.append(f"**Model Version**: {report.get('model_version')}")
        lines.append(f"**Dataset Version**: {report.get('dataset_version', 'N/A')}")
        lines.append(f"**Feature Version**: {report.get('feature_version', 'N/A')}")
        exec_time = report.get('execution_time_seconds')
        lines.append(f"**Execution Time**: {f'{exec_time:.2f}' if exec_time is not None else 'N/A'}s")
        lines.append(f"**Report Timestamp**: {report.get('report_timestamp')}")
        lines.append("")

        metrics = report.get("metrics", {})
        if metrics:
            lines.append("## Metrics")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    lines.append(f"| {k} | {v:.4f} |")
                else:
                    lines.append(f"| {k} | {v} |")

        cv = report.get("cross_validation")
        if cv:
            lines.append("")
            lines.append("## Cross Validation")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Mean | {cv['mean']:.4f} |")
            lines.append(f"| Std | {cv['std']:.4f} |")
            lines.append(f"| Scores | {cv['scores']} |")

        return "\n".join(lines)

    def save_report(self, report: dict[str, Any], filename: str | None = None):
        self._output_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            filename = f"{report['model_name']}_v{report['model_version']}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        json_path = self._output_dir / f"{filename}.json"
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        md_path = self._output_dir / f"{filename}.md"
        with open(md_path, "w") as f:
            f.write(self.format_markdown(report))

        return str(json_path), str(md_path)
