import urllib.request
import json

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "services"
DESCRIPTION = "Health checks for all 6 backend services"


def get_checks(config: ValidationConfig):
    return [
        ModularApiHealth(config),
        IngestServiceHealth(config),
        DatabaseServiceHealth(config),
        EmbeddingServiceHealth(config),
        EnergyServiceHealth(config),
        MlPlatformHealth(config),
    ]


class _ServiceCheck(BaseCheck):
    url_key = ""
    port = 0
    service_name = ""

    def _run(self) -> CheckResult:
        base_url = getattr(self.config, self.url_key)
        # Check /health
        health_ok, health_data = self._check_endpoint(f"{base_url}/health")
        # Check /liveness
        liveness_ok, liveness_data = self._check_endpoint(f"{base_url}/liveness")
        # Check /version
        version_ok, version_data = self._check_endpoint(f"{base_url}/version")

        detail = {}
        if health_data:
            detail["health"] = health_data
        if version_data:
            detail["version"] = version_data

        messages = []
        all_ok = True

        if health_ok:
            messages.append("health OK")
        else:
            messages.append("health FAIL")
            all_ok = False

        if liveness_ok:
            messages.append("liveness OK")
        else:
            messages.append("liveness FAIL")
            all_ok = False

        if version_ok:
            v = version_data.get("version", "?") if isinstance(version_data, dict) else "?"
            messages.append(f"v{v}")
        else:
            messages.append("version FAIL")
            all_ok = False

        return CheckResult(
            name=self.name,
            passed=all_ok,
            message=" | ".join(messages),
            detail=detail,
        )

    def _check_endpoint(self, url):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                return True, json.loads(resp.read().decode())
        except Exception:
            return False, None


class ModularApiHealth(_ServiceCheck):
    name = "Modular API (8000)"
    description = "API gateway health, liveness, version"
    url_key = "modular_api_url"


class IngestServiceHealth(_ServiceCheck):
    name = "Ingest Service (8001)"
    description = "Ingest service health, liveness, version"
    url_key = "ingest_url"


class DatabaseServiceHealth(_ServiceCheck):
    name = "Database Service (8003)"
    description = "Database service health, liveness, version"
    url_key = "db_service_url"


class EmbeddingServiceHealth(_ServiceCheck):
    name = "Embedding Service (8005)"
    description = "Embedding service health, liveness, version"
    url_key = "embedding_url"


class EnergyServiceHealth(_ServiceCheck):
    name = "Energy Service (8006)"
    description = "Energy service health, liveness, version"
    url_key = "energy_url"


class MlPlatformHealth(_ServiceCheck):
    name = "ML Platform (8007)"
    description = "ML platform health, liveness, version"
    url_key = "ml_platform_url"
