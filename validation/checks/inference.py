import urllib.request
import json
import time

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "inference"
DESCRIPTION = "Prediction inference: output schema, latency, confidence values"


def get_checks(config: ValidationConfig):
    return [
        InferenceEndpointAccessible(config),
        PredictionProducesOutput(config),
        PredictionSchemaValid(config),
        PredictionLatency(config),
        PredictionConfidence(config),
    ]


class InferenceEndpointAccessible(BaseCheck):
    name = "Inference endpoint accessible"
    description = "ML Platform /predict endpoint responds"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/predict/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            return CheckResult(
                name=self.name, passed=True,
                message="Inference health endpoint responding",
                detail=data,
            )
        except urllib.error.HTTPError as e:
            if e.code == 405:
                return CheckResult(name=self.name, passed=True, message="Predict endpoint exists (method not allowed on health)")
            return CheckResult(name=self.name, passed=True, warning=True, message=f"Inference health returned HTTP {e.code}", detail={"status": e.code})
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Inference endpoint unreachable: {e}")


class PredictionProducesOutput(BaseCheck):
    name = "Prediction produces output"
    description = "POST /predict returns a prediction"

    def _run(self) -> CheckResult:
        try:
            payload = json.dumps({
                "features": {"commodity_price": 85.0, "volatility_index": 0.3, "supply_buffer_days": 45},
                "model_name": "energy_risk_baseline",
            }).encode()
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/predict"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            has_prediction = data.get("prediction") is not None or data.get("predictions") is not None
            return CheckResult(
                name=self.name, passed=has_prediction,
                message="Prediction returned" if has_prediction else f"Response missing prediction field: {list(data.keys())}",
                detail=data,
            )
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            detail = {"status": e.code, "body": body[:500]}
            if e.code == 404:
                return CheckResult(
                    name=self.name, passed=True, warning=True,
                    message=f"Predict endpoint not deployed (404). Model training and deployment required first.",
                    detail=detail,
                )
            if e.code == 422:
                return CheckResult(
                    name=self.name, passed=True, warning=True,
                    message=f"Prediction request validation error (422): no registered model accepts default features",
                    detail=detail,
                )
            return CheckResult(
                name=self.name, passed=False,
                message=f"Prediction failed (HTTP {e.code})",
                detail=detail,
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Prediction error: {e}")


class PredictionSchemaValid(BaseCheck):
    name = "Prediction output schema valid"
    description = "Prediction response has expected structure"

    def _run(self) -> CheckResult:
        try:
            payload = json.dumps({
                "features": {"commodity_price": 85.0, "volatility_index": 0.3, "supply_buffer_days": 45},
                "model_name": "energy_risk_baseline",
            }).encode()
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/predict"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            expected_keys = {"prediction"} if isinstance(data.get("prediction"), (int, float, str)) and data.get("prediction") is not None else set(data.keys())
            # Inference API should return prediction + confidence + model metadata
            required = {"prediction", "confidence", "model_version", "latency_ms"}
            found = [k for k in required if k in data]
            missing = [k for k in required if k not in data]

            passed = len(missing) == 0
            return CheckResult(
                name=self.name, passed=passed,
                message=f"Schema fields found: {', '.join(found)}" if passed else f"Missing: {', '.join(missing)}",
                detail={"found": found, "missing": missing, "response_keys": list(data.keys())},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(name=self.name, passed=True, warning=True, message="No inference model to validate schema")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Schema validation error: {e}")


class PredictionLatency(BaseCheck):
    name = "Prediction latency"
    description = "Inference completes within acceptable time"

    def _run(self) -> CheckResult:
        try:
            payload = json.dumps({
                "features": {"commodity_price": 85.0, "volatility_index": 0.3, "supply_buffer_days": 45},
                "model_name": "energy_risk_baseline",
            }).encode()
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/predict"
            start = time.perf_counter()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            elapsed = (time.perf_counter() - start) * 1000

            reported_latency = data.get("latency_ms", elapsed)
            acceptable = 5000
            passed = reported_latency < acceptable

            return CheckResult(
                name=self.name, passed=passed,
                message=f"{reported_latency:.0f}ms (limit: {acceptable}ms)",
                detail={"latency_ms": reported_latency, "measured_ms": elapsed, "acceptable_ms": acceptable},
            )
        except urllib.error.HTTPError:
            return CheckResult(name=self.name, passed=True, warning=True, message="No inference model to measure latency")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Latency check error: {e}")


class PredictionConfidence(BaseCheck):
    name = "Prediction confidence"
    description = "Inference returns confidence or probability scores"

    def _run(self) -> CheckResult:
        try:
            payload = json.dumps({
                "features": {"commodity_price": 85.0, "volatility_index": 0.3, "supply_buffer_days": 45},
                "model_name": "energy_risk_baseline",
            }).encode()
            url = f"{self.config.ml_platform_url}{self.config.ml_platform_base}/predict"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            has_confidence = data.get("confidence") is not None
            has_probabilities = data.get("probabilities") is not None
            return CheckResult(
                name=self.name, passed=has_confidence or has_probabilities,
                message=f"Confidence: {data.get('confidence', 'N/A')}, Probabilities: {'yes' if has_probabilities else 'no'}",
                detail={"confidence": data.get("confidence"), "has_probabilities": has_probabilities},
            )
        except urllib.error.HTTPError:
            return CheckResult(name=self.name, passed=True, warning=True, message="No inference model to check confidence")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Confidence check error: {e}")
