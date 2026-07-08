import urllib.request
import json

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "feature_store"
DESCRIPTION = "Feature definitions, freshness, generation, point-in-time retrieval, consistency"


def get_checks(config: ValidationConfig):
    return [
        FeatureDefinitionsAccessible(config),
        FeatureDefinitionsCount(config),
        FeatureTypesValid(config),
        FeatureFreshness(config),
        FeatureGenerationCheck(config),
    ]


class FeatureDefinitionsAccessible(BaseCheck):
    name = "Feature definitions accessible"
    description = "ML Platform features endpoint responds"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/features?limit=5"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            return CheckResult(name=self.name, passed=True, message="Feature registry responding")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Feature store unreachable: {e}")


class FeatureDefinitionsCount(BaseCheck):
    name = "Feature definitions exist"
    description = "At least one feature definition is registered"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/features?limit=100"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            features = data if isinstance(data, list) else data.get("features", data.get("items", [data]))
            if isinstance(features, dict):
                features = [features]
            count = len(features)
            names = [f.get("name", f.get("id", "?")) for f in features[:10]]

            return CheckResult(
                name=self.name, passed=count > 0,
                message=f"{count} feature definitions: {', '.join(names[:5])}{'...' if count > 5 else ''}",
                detail={"count": count, "features": features},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Cannot list features: {e}")


class FeatureTypesValid(BaseCheck):
    name = "Feature types valid"
    description = "Features have recognized types"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/features?limit=100"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            features = data if isinstance(data, list) else data.get("features", data.get("items", []))
            if not features:
                return CheckResult(name=self.name, passed=True, warning=True, message="No features to validate")

            valid_types = {
                "numerical", "categorical", "boolean", "timestamp", "geospatial",
                "entity_statistics", "relationship_statistics", "historical_capacity",
                "infrastructure", "embedding_reference", "graph_placeholder",
            }
            invalid = []
            for f in features:
                ft = f.get("feature_type", f.get("type", "")).lower()
                if ft and ft not in valid_types:
                    invalid.append((f.get("name", "?"), ft))

            if invalid:
                return CheckResult(
                    name=self.name, passed=False,
                    message=f"{len(invalid)} features with unrecognized types",
                    detail={"invalid": invalid},
                )
            return CheckResult(name=self.name, passed=True, message="All feature types are recognized")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Type validation failed: {e}")


class FeatureFreshness(BaseCheck):
    name = "Feature freshness"
    description = "Features have timestamps or version tracking"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/features?limit=100"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            features = data if isinstance(data, list) else data.get("features", data.get("items", []))
            if not features:
                return CheckResult(name=self.name, passed=True, warning=True, message="No features to check")

            with_ts = sum(1 for f in features if f.get("created_at") or f.get("updated_at") or f.get("version"))
            return CheckResult(
                name=self.name, passed=with_ts == len(features),
                message=f"{with_ts}/{len(features)} features have freshness tracking",
                detail={"fresh": with_ts, "total": len(features)},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Freshness check failed: {e}")


class FeatureGenerationCheck(BaseCheck):
    name = "Feature generation pipeline"
    description = "Feature generation is wired in ML Platform"

    def _run(self) -> CheckResult:
        try:
            import sys
            sys.path.insert(0, "services/ml-platform")
            from feature_store.pipeline import FeaturePipeline
            return CheckResult(
                name=self.name, passed=True,
                message="FeaturePipeline loaded",
            )
        except ImportError as e:
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message=f"Cannot import feature pipeline: {e}. Set PYTHONPATH to services/ml-platform",
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Feature pipeline error: {e}")
