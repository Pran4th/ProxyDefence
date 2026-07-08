import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR

logger = get_logger(__name__)

_DEFAULT_ARCHITECTURES = {
    "logistic_regression": "Linear probabilistic classifier with sigmoid output",
    "decision_tree": "Tree-based decision boundaries with Gini impurity splitting",
    "random_forest": "Ensemble of decision trees with bootstrap aggregation",
    "xgboost": "Gradient-boosted decision trees with regularized boosting",
    "lightgbm": "Gradient-boosted decision trees with GOSS/EFB optimizations",
    "catboost": "Gradient-boosted decision trees with ordered boosting",
}


@dataclass
class ModelCard:
    model_name: str
    model_version: int
    model_type: str
    task: str
    dataset_name: str
    dataset_version: int
    intended_use: str = ""
    limitations: str = ""
    ethical_considerations: str = ""
    evaluation_metrics: dict = field(default_factory=dict)
    training_params: dict = field(default_factory=dict)
    training_date: str = ""
    owner: str = "system"
    model_architecture: str = ""
    feature_count: int = 0
    training_duration_seconds: float = 0.0
    inference_latency_ms: float | None = None
    model_size_kb: float | None = None
    bias_assessment: str = ""
    out_of_scope_usage: str = ""
    dependencies: list[str] = field(default_factory=list)
    license: str = "MIT"
    references: list[str] = field(default_factory=list)


class ModelCardGenerator:
    def generate(self, model_metadata: dict,
                 experiment_result: dict | None = None) -> ModelCard:
        merged = dict(model_metadata)
        if experiment_result:
            for k, v in experiment_result.items():
                if k not in merged or not merged.get(k):
                    merged[k] = v
        card = ModelCard(
            model_name=merged.get("model_name", merged.get("name", "unknown_model")),
            model_version=int(merged.get("model_version", 1)),
            model_type=merged.get("model_type", merged.get("type", "unknown")),
            task=merged.get("task", merged.get("experiment_type", "classification")),
            dataset_name=merged.get("dataset_name", merged.get("dataset", {}).get("name", "unknown")),
            dataset_version=int(merged.get("dataset_version", merged.get("dataset", {}).get("version", 1))),
            intended_use=merged.get("intended_use", ""),
            limitations=merged.get("limitations", ""),
            ethical_considerations=merged.get("ethical_considerations", ""),
            evaluation_metrics=merged.get("evaluation_metrics", merged.get("metrics", {})),
            training_params=merged.get("training_params", merged.get("config", {}).get("model", {}).get("parameters", {})),
            training_date=merged.get("training_date", merged.get("created_at", datetime.now().isoformat())),
            owner=merged.get("owner", merged.get("author", "system")),
            model_architecture=merged.get("model_architecture", ""),
            feature_count=int(merged.get("feature_count", merged.get("dataset", {}).get("feature_count", 0))),
            training_duration_seconds=float(merged.get("training_duration_seconds", 0.0)),
            inference_latency_ms=merged.get("inference_latency_ms"),
            model_size_kb=merged.get("model_size_kb"),
            bias_assessment=merged.get("bias_assessment", ""),
            out_of_scope_usage=merged.get("out_of_scope_usage", ""),
            dependencies=merged.get("dependencies", merged.get("config", {}).get("dependencies", [])),
            license=merged.get("license", "MIT"),
            references=merged.get("references", []),
        )
        return self.fill_defaults(card)

    async def to_markdown(self, card: ModelCard) -> str:
        lines = [
            f"# Model Card: {card.model_name}",
            "",
            f"**Version:** {card.model_version}  ",
            f"**Type:** {card.model_type}  ",
            f"**Task:** {card.task}  ",
            f"**Date:** {card.training_date}  ",
            f"**Owner:** {card.owner}  ",
            f"**License:** {card.license}  ",
            "",
            "---",
            "",
            "## Model Architecture",
            card.model_architecture,
            "",
            f"**Feature Count:** {card.feature_count}  ",
            f"**Training Duration:** {card.training_duration_seconds:.2f}s  ",
            f"**Inference Latency:** {card.inference_latency_ms if card.inference_latency_ms is not None else 'N/A'} ms  ",
            f"**Model Size:** {card.model_size_kb if card.model_size_kb is not None else 'N/A'} KB  ",
            "",
            "---",
            "",
            "## Dataset",
            "",
            f"**Name:** {card.dataset_name}  ",
            f"**Version:** {card.dataset_version}  ",
            "",
            "---",
            "",
            "## Intended Use",
            card.intended_use or "No description provided.",
            "",
            "---",
            "",
            "## Evaluation Metrics",
            "",
        ]
        if card.evaluation_metrics:
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for k, v in card.evaluation_metrics.items():
                val = f"{v:.4f}" if isinstance(v, float) else str(v)
                lines.append(f"| {k} | {val} |")
        else:
            lines.append("No evaluation metrics recorded.")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Training Parameters")
        if card.training_params:
            lines.append("| Parameter | Value |")
            lines.append("|-----------|-------|")
            for k, v in card.training_params.items():
                lines.append(f"| {k} | {v} |")
        else:
            lines.append("No training parameters recorded.")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Limitations")
        lines.append(card.limitations or "None documented.")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Ethical Considerations")
        lines.append(card.ethical_considerations or "None documented.")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Bias Assessment")
        lines.append(card.bias_assessment or "Not assessed.")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Out-of-Scope Usage")
        lines.append(card.out_of_scope_usage or "Not specified.")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Dependencies")
        if card.dependencies:
            for dep in card.dependencies:
                lines.append(f"- {dep}")
        else:
            lines.append("No dependencies listed.")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## References")
        if card.references:
            for ref in card.references:
                lines.append(f"- {ref}")
        else:
            lines.append("No references.")
        return "\n".join(lines) + "\n"

    async def to_json(self, card: ModelCard) -> str:
        return json.dumps(asdict(card), indent=2, default=str)

    async def save(self, card: ModelCard, output_dir: str,
                   formats: list[str] = None) -> dict[str, str]:
        if formats is None:
            formats = ["md", "json"]
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = {}
        slug = card.model_name.lower().replace(" ", "_")
        if "md" in formats:
            md_path = str(out / f"{slug}_v{card.model_version}_card.md")
            md_content = await self.to_markdown(card)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            paths["md"] = md_path
        if "json" in formats:
            json_path = str(out / f"{slug}_v{card.model_version}_card.json")
            json_content = await self.to_json(card)
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(json_content)
            paths["json"] = json_path
        logger.info("model card saved to %s", paths)
        return paths

    async def from_model_version(self, model_uuid: str, pool=None) -> ModelCard:
        if pool is None:
            from db import get_pool
            pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.model_versions WHERE uuid = $1", model_uuid,
        )
        if not row:
            raise ValueError(f"Model version not found: {model_uuid}")
        metadata = dict(row)
        metrics = {}
        if "metrics" in metadata and isinstance(metadata["metrics"], str):
            metrics = json.loads(metadata["metrics"])
        elif "metrics" in metadata and isinstance(metadata["metrics"], dict):
            metrics = metadata["metrics"]
        params = {}
        if "parameters" in metadata and isinstance(metadata["parameters"], str):
            params = json.loads(metadata["parameters"])
        elif "parameters" in metadata and isinstance(metadata["parameters"], dict):
            params = metadata["parameters"]
        arch = metadata.get("architecture", "")
        if not arch:
            arch = _DEFAULT_ARCHITECTURES.get(metadata.get("model_type", ""), "")
        card = ModelCard(
            model_name=metadata.get("model_name", "unknown"),
            model_version=int(metadata.get("version", metadata.get("model_version", 1))),
            model_type=metadata.get("model_type", "unknown"),
            task=metadata.get("task", "classification"),
            dataset_name=metadata.get("dataset_name", "unknown"),
            dataset_version=int(metadata.get("dataset_version", 1)),
            feature_count=int(metadata.get("feature_count", 0)),
            evaluation_metrics=metrics,
            training_params=params,
            training_date=metadata.get("created_at", "").isoformat() if hasattr(metadata.get("created_at"), "isoformat") else str(metadata.get("created_at", "")),
            owner=metadata.get("owner", metadata.get("author", "system")),
            model_architecture=arch,
            training_duration_seconds=float(metadata.get("training_duration_seconds", 0)),
            inference_latency_ms=metadata.get("inference_latency_ms"),
            model_size_kb=metadata.get("model_size_kb"),
        )
        return self.fill_defaults(card)

    async def from_experiment_run(self, run_uuid: str, pool=None) -> ModelCard:
        if pool is None:
            from db import get_pool
            pool = await get_pool()
        run = await pool.fetchrow(
            "SELECT * FROM ml.experiment_runs WHERE uuid = $1", run_uuid,
        )
        if not run:
            raise ValueError(f"Experiment run not found: {run_uuid}")
        exp = await pool.fetchrow(
            "SELECT * FROM ml.experiments WHERE uuid = $1", run["experiment_uuid"],
        )
        merged = dict(run)
        if exp:
            merged["experiment_type"] = exp.get("experiment_type", "classification")
            merged["author"] = exp.get("author", "system")
            merged["experiment_name"] = exp.get("name", "")
        metrics = {}
        if "metrics" in merged and isinstance(merged["metrics"], str):
            metrics = json.loads(merged["metrics"])
        elif "metrics" in merged and isinstance(merged["metrics"], dict):
            metrics = merged["metrics"]
        params = {}
        if "params" in merged and isinstance(merged["params"], str):
            params = json.loads(merged["params"])
        elif "params" in merged and isinstance(merged["params"], dict):
            params = merged["params"]
        config = {}
        if "config" in merged and isinstance(merged["config"], str):
            config = json.loads(merged["config"])
        elif "config" in merged and isinstance(merged["config"], dict):
            config = merged["config"]
        model_type = config.get("model", {}).get("type", merged.get("model_type", "unknown"))
        dataset_info = config.get("dataset", {})
        arch = _DEFAULT_ARCHITECTURES.get(model_type, "")
        card = ModelCard(
            model_name=merged.get("run_name", f"run_{run_uuid[:8]}"),
            model_version=int(merged.get("run_number", 1)),
            model_type=model_type,
            task=merged.get("experiment_type", "classification"),
            dataset_name=dataset_info.get("name", "unknown"),
            dataset_version=int(dataset_info.get("version", 1)),
            feature_count=int(dataset_info.get("feature_count", dataset_info.get("n_features", 0))),
            evaluation_metrics=metrics,
            training_params=params,
            training_date=merged.get("start_time", "").isoformat() if hasattr(merged.get("start_time"), "isoformat") else str(merged.get("start_time", "")),
            owner=merged.get("author", "system"),
            model_architecture=arch,
            training_duration_seconds=float(merged.get("duration_seconds", 0)),
        )
        return self.fill_defaults(card)

    def fill_defaults(self, card: ModelCard) -> ModelCard:
        if not card.model_architecture:
            card.model_architecture = _DEFAULT_ARCHITECTURES.get(card.model_type, "No description available.")
        if not card.intended_use:
            card.intended_use = f"Model for {card.task} tasks using {card.model_type} algorithm."
        if not card.limitations:
            card.limitations = f"Performance depends on data quality and distribution. May not generalize to domains outside {card.dataset_name}."
        if not card.ethical_considerations:
            card.ethical_considerations = "Model predictions should be reviewed by domain experts before acting on them."
        if not card.bias_assessment:
            card.bias_assessment = "No formal bias audit has been performed. Users should evaluate for their specific use case."
        if not card.out_of_scope_usage:
            card.out_of_scope_usage = "This model should not be used for high-stakes decisions without human oversight."
        if not card.dependencies:
            card.dependencies = ["scikit-learn", "xgboost", "pandas", "numpy"]
        return card
