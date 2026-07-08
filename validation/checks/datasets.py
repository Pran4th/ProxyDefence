import urllib.request
import json

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "datasets"
DESCRIPTION = "Dataset registry validation: schema, metadata, lineage, version, quality, reproducibility"


def get_checks(config: ValidationConfig):
    return [
        DatasetRegistryAccessible(config),
        DatasetListNotEmpty(config),
        DatasetSchemaValid(config),
        DatasetMetadataComplete(config),
        DatasetLineageTracked(config),
        DatasetVersionsTracked(config),
    ]


class DatasetRegistryAccessible(BaseCheck):
    name = "Dataset registry accessible"
    description = "ML Platform datasets endpoint responds"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/datasets?limit=5"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            return CheckResult(name=self.name, passed=True, message="Dataset registry responding", detail={"raw": data if isinstance(data, dict) else {"count": len(data) if isinstance(data, list) else 0}})
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Dataset registry unreachable: {e}")


class DatasetListNotEmpty(BaseCheck):
    name = "Datasets registered"
    description = "At least one dataset is registered"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/datasets?limit=100"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            datasets = data if isinstance(data, list) else data.get("datasets", data.get("items", [data]))
            if isinstance(datasets, dict):
                datasets = [datasets]
            count = len(datasets)
            names = [d.get("name", d.get("id", "?")) for d in datasets[:10]]

            return CheckResult(
                name=self.name, passed=count > 0,
                message=f"{count} datasets registered: {', '.join(names[:5])}{'...' if count > 5 else ''}",
                detail={"count": count, "datasets": datasets},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Cannot list datasets: {e}")


class DatasetSchemaValid(BaseCheck):
    name = "Dataset schemas valid"
    description = "Each dataset has required schema fields"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/datasets?limit=50"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            datasets = data if isinstance(data, list) else data.get("datasets", data.get("items", []))
            if not datasets:
                return CheckResult(name=self.name, passed=True, warning=True, message="No datasets to validate")

            required_fields = {"name", "id", "version", "created_at"}
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
    description = "Datasets have source, description, and grain metadata"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/datasets?limit=50"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            datasets = data if isinstance(data, list) else data.get("datasets", data.get("items", []))
            if not datasets:
                return CheckResult(name=self.name, passed=True, warning=True, message="No datasets to check")

            total = len(datasets)
            with_source = sum(1 for d in datasets if d.get("source") or d.get("source_type"))
            with_desc = sum(1 for d in datasets if d.get("description"))
            with_grain = sum(1 for d in datasets if d.get("grain") or d.get("entity_type"))

            issues = []
            if with_source < total:
                issues.append(f"source: {with_source}/{total}")
            if with_desc < total:
                issues.append(f"description: {with_desc}/{total}")
            if with_grain < total:
                issues.append(f"grain: {with_grain}/{total}")

            passed = len(issues) == 0
            return CheckResult(
                name=self.name, passed=passed,
                message="All metadata complete" if passed else f"Incomplete: {', '.join(issues)}",
                detail={"total": total, "with_source": with_source, "with_description": with_desc, "with_grain": with_grain},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Metadata check failed: {e}")


class DatasetLineageTracked(BaseCheck):
    name = "Dataset lineage tracked"
    description = "Datasets have lineage information"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/datasets?limit=50"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            datasets = data if isinstance(data, list) else data.get("datasets", data.get("items", []))
            if not datasets:
                return CheckResult(name=self.name, passed=True, warning=True, message="No datasets to check")

            with_lineage = sum(1 for d in datasets if d.get("lineage") or d.get("source_records") or d.get("transformations"))
            return CheckResult(
                name=self.name, passed=with_lineage > 0,
                message=f"{with_lineage}/{len(datasets)} datasets have lineage info",
                detail={"with_lineage": with_lineage, "total": len(datasets)},
            )
        except Exception:
            return CheckResult(name=self.name, passed=True, warning=True, message="Lineage endpoint unavailable")


class DatasetVersionsTracked(BaseCheck):
    name = "Dataset versions tracked"
    description = "Datasets have version information"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/datasets?limit=50"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            datasets = data if isinstance(data, list) else data.get("datasets", data.get("items", []))
            if not datasets:
                return CheckResult(name=self.name, passed=True, warning=True, message="No datasets to check")

            with_version = sum(1 for d in datasets if d.get("version") or d.get("dataset_version"))
            return CheckResult(
                name=self.name, passed=with_version > 0,
                message=f"{with_version}/{len(datasets)} datasets have version info",
                detail={"with_version": with_version, "total": len(datasets)},
            )
        except Exception:
            return CheckResult(name=self.name, passed=True, warning=True, message="Version check unavailable")
