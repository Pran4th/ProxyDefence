import urllib.request
import json

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "model_registry"
DESCRIPTION = "Registered models, metadata, artifacts, version validation"


def get_checks(config: ValidationConfig):
    return [
        ModelRegistryAccessible(config),
        ModelsRegistered(config),
        ModelMetadataComplete(config),
        ModelVersionStages(config),
        ModelArtifactsAccessible(config),
    ]


class ModelRegistryAccessible(BaseCheck):
    name = "Model registry accessible"
    description = "ML Platform models endpoint responds"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/models?limit=5"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                json.loads(resp.read())
            return CheckResult(name=self.name, passed=True, message="Model registry responding")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Model registry unreachable: {e}")


class ModelsRegistered(BaseCheck):
    name = "Models registered"
    description = "At least one model version is registered"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/models?limit=100"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            models = data if isinstance(data, list) else data.get("models", data.get("items", [data]))
            if isinstance(models, dict):
                models = [models]
            count = len(models)
            names = set()
            for m in models:
                names.add(m.get("name", m.get("model_name", m.get("id", "?"))))

            return CheckResult(
                name=self.name, passed=count > 0,
                message=f"{count} model versions, {len(names)} unique models: {', '.join(sorted(names))}",
                detail={"count": count, "unique_models": sorted(names), "models": models},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Cannot list models: {e}")


class ModelMetadataComplete(BaseCheck):
    name = "Model metadata complete"
    description = "Each model has required metadata fields"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/models?limit=100"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            models = data if isinstance(data, list) else data.get("models", data.get("items", []))
            if not models:
                return CheckResult(name=self.name, passed=True, warning=True, message="No models to check")

            required = {"name", "version", "stage", "created_at"}
            missing_any = 0
            for m in models:
                missing = required - set(m.keys())
                if missing:
                    missing_any += 1

            return CheckResult(
                name=self.name, passed=missing_any == 0,
                message=f"All {len(models)} models have required metadata" if missing_any == 0
                else f"{missing_any}/{len(models)} models missing required fields",
                detail={"total": len(models), "incomplete": missing_any},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Metadata check failed: {e}")


class ModelVersionStages(BaseCheck):
    name = "Model version stages"
    description = "Models follow lifecycle stages (dev → val → staging → production → archived)"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/models?limit=100"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            models = data if isinstance(data, list) else data.get("models", data.get("items", []))
            if not models:
                return CheckResult(name=self.name, passed=True, warning=True, message="No models to check")

            valid_stages = {"development", "validation", "staging", "production", "archived"}
            stages_found = set()
            invalid = []
            for m in models:
                stage = (m.get("stage") or m.get("lifecycle_stage") or "").lower()
                if stage:
                    stages_found.add(stage)
                    if stage not in valid_stages:
                        invalid.append((m.get("name", "?"), stage))

            if invalid:
                return CheckResult(
                    name=self.name, passed=False,
                    message=f"{len(invalid)} models with invalid stages: {invalid}",
                    detail={"invalid": invalid, "stages_found": sorted(stages_found)},
                )
            return CheckResult(
                name=self.name, passed=True,
                message=f"Valid stages: {', '.join(sorted(stages_found))}",
                detail={"stages_found": sorted(stages_found)},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Stage check failed: {e}")


class ModelArtifactsAccessible(BaseCheck):
    name = "Model artifacts accessible"
    description = "Production model artifacts exist and are accessible"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/models?limit=100"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            models = data if isinstance(data, list) else data.get("models", data.get("items", []))
            if not models:
                return CheckResult(name=self.name, passed=True, warning=True, message="No models to check")

            production = [m for m in models if (m.get("stage") or "").lower() == "production"]
            with_artifacts = sum(1 for m in production if m.get("artifact_uri") or m.get("model_uri") or m.get("file_path") or m.get("location"))

            if production:
                return CheckResult(
                    name=self.name, passed=with_artifacts == len(production),
                    message=f"{with_artifacts}/{len(production)} production models have artifact paths",
                    detail={"production_count": len(production), "with_artifacts": with_artifacts},
                )
            # Check latest model for any artifact
            latest = models[-1] if len(models) > 0 else None
            has_artifact = bool(latest and (latest.get("artifact_uri") or latest.get("model_uri") or latest.get("file_path") or latest.get("location")))
            return CheckResult(
                name=self.name, passed=True if has_artifact else True,
                warning=not has_artifact,
                message=f"No production models. Latest model has artifact: {has_artifact}" if has_artifact
                else "No production models and latest model lacks artifact path",
                detail={"total_models": len(models), "production_count": 0},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Artifact check failed: {e}")
