from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from data_acquisition.source_registry import DATASET_REGISTRY, SourceRegistry

logger = get_logger(__name__)


class DatasetResolver:
    def __init__(self) -> None:
        self._registry = SourceRegistry()
        for sd in DATASET_REGISTRY:
            self._registry.register(sd)

    async def resolve_dataset(
        self,
        dataset_spec: str,
        version: str | None = None,
        pool=None,
    ) -> dict:
        source_def = self._registry.get(dataset_spec)
        if source_def:
            res_version = version or source_def.version
            return {
                "path": f"./datasets/raw/{dataset_spec}/{res_version}",
                "source": dataset_spec,
                "display_name": source_def.display_name,
                "description": source_def.description,
                "category": source_def.category,
                "schema": source_def.expected_schema,
                "version": res_version,
                "license": source_def.license,
                "citation": source_def.citation,
                "tags": source_def.tags,
                "features": list(source_def.expected_schema.keys()),
                "target": None,
            }

        from datasets.catalog import DatasetCatalog

        catalog = DatasetCatalog()
        entry = await catalog.get(dataset_spec)
        if entry:
            res_version = version or "1"
            return {
                "path": f"./datasets/processed/{dataset_spec}/{res_version}",
                "source": entry.get("source", dataset_spec),
                "display_name": dataset_spec,
                "description": entry.get("description", ""),
                "category": entry.get("dataset_type", ""),
                "schema": {},
                "version": res_version,
                "license": "",
                "citation": "",
                "tags": entry.get("tags", []),
                "features": [],
                "target": None,
            }

        if dataset_spec.startswith("."):
            p = Path(dataset_spec).resolve()
            return {
                "path": str(p),
                "source": p.stem,
                "display_name": p.stem,
                "description": f"Local file: {p.name}",
                "category": "local",
                "schema": {},
                "version": version or "1",
                "license": "",
                "citation": "",
                "tags": [],
                "features": [],
                "target": None,
            }

        raise ValueError(f"Dataset not found: {dataset_spec}")

    async def resolve_for_experiment(
        self,
        dataset_spec: str,
        experiment_config: dict,
        pool=None,
    ) -> dict:
        resolved = await self.resolve_dataset(dataset_spec, pool=pool)

        experiment_config.setdefault("experiment", {})
        experiment_config.setdefault("model", {})
        experiment_config.setdefault("dataset", {})

        experiment_config["dataset"]["name"] = dataset_spec
        experiment_config["dataset"]["version"] = resolved.get("version", "1")
        experiment_config["dataset"]["path"] = resolved.get("path", "")

        if resolved.get("schema"):
            experiment_config["dataset"]["feature_names"] = resolved.get("features", [])
        if resolved.get("target"):
            experiment_config["dataset"]["target_column"] = resolved["target"]

        return experiment_config

    async def list_available_datasets(self, pool=None) -> list[dict]:
        datasets: list[dict] = []
        for sd in self._registry.list_sources():
            datasets.append({
                "name": sd.name,
                "display_name": sd.display_name,
                "description": sd.description,
                "category": sd.category,
                "version": sd.version,
                "tags": sd.tags,
                "connector_type": sd.connector_type,
                "feature_count": len(sd.expected_schema),
            })
        return datasets

    async def validate_dataset_ref(
        self, dataset_spec: str, pool=None
    ) -> list[str]:
        errors: list[str] = []
        source_def = self._registry.get(dataset_spec)
        if source_def is not None:
            return errors

        from datasets.catalog import DatasetCatalog

        catalog = DatasetCatalog()
        entry = await catalog.get(dataset_spec)
        if entry is None and not dataset_spec.startswith("."):
            errors.append(
                f"Dataset '{dataset_spec}' not found in registry or catalog"
            )
        return errors


class ExperimentDatasetResolver:
    def __init__(self) -> None:
        self._resolver = DatasetResolver()

    async def prepare_experiment(
        self,
        experiment_name: str,
        config: dict,
        pool=None,
    ) -> dict:
        dataset_spec = config.get("dataset")
        if isinstance(dataset_spec, str):
            enriched = await self._resolver.resolve_for_experiment(
                dataset_spec, config, pool=pool
            )
        else:
            enriched = config
        enriched.setdefault("experiment", {})
        enriched["experiment"].setdefault("name", experiment_name)
        return enriched

    async def get_dataset_card(
        self, dataset_spec: str, pool=None
    ) -> dict:
        resolved = await self._resolver.resolve_dataset(dataset_spec, pool=pool)
        source_def = self._resolver._registry.get(dataset_spec)

        card = {
            "name": dataset_spec,
            "display_name": resolved.get("display_name", dataset_spec),
            "description": resolved.get("description", ""),
            "category": resolved.get("category", ""),
            "version": resolved.get("version", ""),
            "source": resolved.get("source", ""),
            "path": resolved.get("path", ""),
            "schema": resolved.get("schema", {}),
            "feature_count": len(resolved.get("features", [])),
            "features": resolved.get("features", []),
            "target": resolved.get("target"),
        }

        if source_def:
            card.update({
                "license": source_def.license,
                "citation": source_def.citation,
                "tags": source_def.tags,
                "update_frequency": source_def.update_frequency,
                "connector_type": source_def.connector_type,
            })

        return card
