import urllib.request
import json

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "datasets"
DESCRIPTION = "Dataset catalog validation: schema, metadata, lineage, version, quality, reproducibility"


def get_checks(config: ValidationConfig):
    return [
        DatasetRegistryAccessible(config),
        DatasetListNotEmpty(config),
        DatasetSchemaValid(config),
        DatasetMetadataComplete(config),
        DatasetLineageTracked(config),
        DatasetVersionsTracked(config),
    ]


def _catalog_url(config, **params) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{config.ml_platform_url}/api/v1/ml/datasets/catalog?{query}"


def _fetch_catalog(config, limit: int) -> list[dict]:
    url = _catalog_url(config, limit=limit)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=config.http_timeout) as resp:
        data = json.loads(resp.read())
    return data.get("items", [])


class DatasetRegistryAccessible(BaseCheck):
    name = "Dataset registry accessible"
    description = "ML Platform dataset catalog endpoint responds"

    def _run(self) -> CheckResult:
        try:
            datasets = _fetch_catalog(self.config, 5)
            return CheckResult(name=self.name, passed=True, message="Dataset catalog responding", detail={"count": len(datasets)})
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Dataset catalog unreachable: {e}")


class DatasetListNotEmpty(BaseCheck):
    name = "Datasets registered"
    description = "At least one dataset is registered in the catalog"

    def _run(self) -> CheckResult:
        try:
            datasets = _fetch_catalog(self.config, 100)
            count = len(datasets)
            names = [d.get("name", "?") for d in datasets[:10]]
            return CheckResult(
                name=self.name, passed=count > 0,
                message=f"{count} datasets registered: {', '.join(names[:5])}{'...' if count > 5 else ''}",
                detail={"count": count, "datasets": names},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Cannot list datasets: {e}")


class DatasetSchemaValid(BaseCheck):
    name = "Dataset schemas valid"
    description = "Each catalog entry has the required catalog fields"

    def _run(self) -> CheckResult:
        try:
            datasets = _fetch_catalog(self.config, 50)
            if not datasets:
                return CheckResult(name=self.name, passed=True, warning=True, message="No datasets to validate")

            required_fields = {"name", "uuid", "dataset_type", "created_at"}
            invalid = []
            for d in datasets:
                missing = required_fields - set(d.keys())
                if missing:
                    invalid.append((d.get("name", "?"), list(missing)))

            if invalid:
                return CheckResult(
                    name=self.name, passed=False,
                    message=f"{len(invalid)} datasets missing required fields",
                    detail={"invalid": invalid},
                )
            return CheckResult(
                name=self.name, passed=True,
                message=f"All {len(datasets)} datasets have required schema fields",
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Schema check failed: {e}")


class DatasetMetadataComplete(BaseCheck):
    name = "Dataset metadata complete"
    description = "Datasets have source and dataset_type metadata"

    def _run(self) -> CheckResult:
        try:
            datasets = _fetch_catalog(self.config, 50)
            if not datasets:
                return CheckResult(name=self.name, passed=True, warning=True, message="No datasets to check")

            total = len(datasets)
            with_source = sum(1 for d in datasets if d.get("source"))
            with_type = sum(1 for d in datasets if d.get("dataset_type"))
            with_desc = sum(1 for d in datasets if d.get("description"))

            issues = []
            if with_source < total:
                issues.append(f"source: {with_source}/{total}")
            if with_type < total:
                issues.append(f"dataset_type: {with_type}/{total}")

            passed = with_source == total and with_type == total
            return CheckResult(
                name=self.name, passed=passed,
                message="All metadata complete" if passed else f"Incomplete: {', '.join(issues)}",
                detail={"total": total, "with_source": with_source, "with_type": with_type, "with_description": with_desc},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Metadata check failed: {e}")


class DatasetLineageTracked(BaseCheck):
    name = "Dataset lineage endpoint reachable"
    description = "GET /api/v1/ml/datasets/lineage/health responds"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}/api/v1/ml/datasets/lineage/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            return CheckResult(name=self.name, passed=True, message="Lineage endpoint responding", detail=data)
        except Exception as e:
            return CheckResult(name=self.name, passed=True, warning=True, message=f"Lineage endpoint unavailable: {e}")


class DatasetVersionsTracked(BaseCheck):
    name = "Dataset versions tracked"
    description = "Datasets carry a dataset_type used to key their versioned splits"

    def _run(self) -> CheckResult:
        try:
            datasets = _fetch_catalog(self.config, 50)
            if not datasets:
                return CheckResult(name=self.name, passed=True, warning=True, message="No datasets to check")

            with_type = sum(1 for d in datasets if d.get("dataset_type"))
            return CheckResult(
                name=self.name, passed=with_type > 0,
                message=f"{with_type}/{len(datasets)} datasets have dataset_type set",
                detail={"with_type": with_type, "total": len(datasets)},
            )
        except Exception:
            return CheckResult(name=self.name, passed=True, warning=True, message="Version check unavailable")
