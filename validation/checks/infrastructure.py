import base64
import subprocess
import urllib.request
import json
import socket

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig


def _es_auth_header(config) -> dict:
    creds = base64.b64encode(f"{config.elasticsearch_user}:{config.elasticsearch_password}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}

CATEGORY = "infrastructure"
DESCRIPTION = "Docker, PostgreSQL, Kafka, Elasticsearch, pgvector, Redis, API Gateway, Frontend"


def get_checks(config: ValidationConfig):
    return [
        DockerContainersRunning(config),
        PostgresConnectivity(config),
        PostgresPgvectorExtension(config),
        KafkaConnectivity(config),
        ElasticsearchHealth(config),
        RedisConnectivity(config),
        ApiGatewayHealth(config),
        FrontendAvailability(config),
    ]


class DockerContainersRunning(BaseCheck):
    name = "Docker containers running"
    description = "All required Docker containers are up"

    def _run(self) -> CheckResult:
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return CheckResult(name=self.name, passed=False, message=f"Docker not accessible: {result.stderr.strip()}")

            containers = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
            expected = ["postgres", "elasticsearch", "kafka"]
            missing = [e for e in expected if e not in " ".join(containers).lower()]

            if missing:
                return CheckResult(
                    name=self.name, passed=False,
                    message=f"Missing containers: {', '.join(missing)}. Running: {', '.join(containers)}",
                    detail={"running": containers, "missing": missing},
                )
            return CheckResult(
                name=self.name, passed=True,
                message=f"All {len(expected)} expected containers running",
                detail={"running": containers},
            )
        except FileNotFoundError:
            return CheckResult(name=self.name, passed=False, message="Docker CLI not found")
        except subprocess.TimeoutExpired:
            return CheckResult(name=self.name, passed=False, message="Docker command timed out")


class PostgresConnectivity(BaseCheck):
    name = "PostgreSQL connectivity"
    description = "Can connect to PostgreSQL and execute queries"

    def _run(self) -> CheckResult:
        try:
            import asyncpg
        except ImportError:
            return CheckResult(name=self.name, passed=False, message="asyncpg not installed")

        try:
            import asyncio

            async def check():
                conn = await asyncpg.connect(
                    host=self.config.postgres_host,
                    port=self.config.postgres_port,
                    user=self.config.postgres_user,
                    password=self.config.postgres_password,
                    database=self.config.postgres_db,
                    timeout=self.config.db_timeout,
                )
                val = await conn.fetchval("SELECT 1")
                version = await conn.fetchval("SELECT version()")
                await conn.close()
                return val, version

            val, version = asyncio.run(check())
            if val == 1:
                return CheckResult(
                    name=self.name, passed=True,
                    message=f"Connected. {version.split(',')[0] if version else ''}",
                    detail={"version": version or ""},
                )
            return CheckResult(name=self.name, passed=False, message="SELECT 1 returned unexpected value")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Connection failed: {e}")


class PostgresPgvectorExtension(BaseCheck):
    name = "pgvector extension"
    description = "pgvector extension is installed in PostgreSQL"

    def _run(self) -> CheckResult:
        try:
            import asyncpg
        except ImportError:
            return CheckResult(name=self.name, passed=False, message="asyncpg not installed")

        try:
            import asyncio

            async def check():
                conn = await asyncpg.connect(
                    host=self.config.postgres_host,
                    port=self.config.postgres_port,
                    user=self.config.postgres_user,
                    password=self.config.postgres_password,
                    database=self.config.postgres_db,
                    timeout=self.config.db_timeout,
                )
                installed = await conn.fetchval(
                    "SELECT TRUE FROM pg_extension WHERE extname = 'vector'"
                )
                version = await conn.fetchval(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                ) if installed else None
                await conn.close()
                return installed, version

            installed, version = asyncio.run(check())
            if installed:
                return CheckResult(
                    name=self.name, passed=True,
                    message=f"pgvector v{version} installed",
                    detail={"version": version},
                )
            return CheckResult(
                name=self.name, passed=False, warning=True,
                message="pgvector extension not installed",
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Cannot check pgvector: {e}")


class KafkaConnectivity(BaseCheck):
    name = "Kafka connectivity"
    description = "Can connect to Kafka broker and list topics"

    def _run(self) -> CheckResult:
        # First try a basic TCP port check
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((self.config.kafka_host, self.config.kafka_port))
            s.close()
        except Exception:
            return CheckResult(name=self.name, passed=False, message=f"Kafka port {self.config.kafka_port} not reachable")

        # Then try the full Kafka protocol check
        try:
            from confluent_kafka import Producer
            p = Producer({"bootstrap.servers": f"{self.config.kafka_host}:{self.config.kafka_port}"})
            metadata = p.list_topics(timeout=self.config.kafka_timeout)
            topics = list(metadata.topics.keys())
            return CheckResult(
                name=self.name, passed=True,
                message=f"Connected. {len(topics)} topics found",
                detail={"topics": topics, "broker": f"{self.config.kafka_host}:{self.config.kafka_port}"},
            )
        except ImportError:
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message=f"Port open, but confluent_kafka not installed for topic listing",
                detail={"host": self.config.kafka_host, "port": self.config.kafka_port},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Kafka protocol error: {e}")


class ElasticsearchHealth(BaseCheck):
    name = "Elasticsearch health"
    description = "Elasticsearch cluster is healthy"

    def _run(self) -> CheckResult:
        try:
            url = f"http://{self.config.elasticsearch_host}:{self.config.elasticsearch_port}/_cluster/health"
            req = urllib.request.Request(url, headers=_es_auth_header(self.config))
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            status = data.get("status", "unknown")
            passed = status in ("green", "yellow")
            return CheckResult(
                name=self.name, passed=passed,
                message=f"Cluster status: {status}",
                detail=data,
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"ES connection failed: {e}")


class RedisConnectivity(BaseCheck):
    name = "Redis connectivity"
    description = "Redis is reachable (if enabled)"

    def _run(self) -> CheckResult:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((self.config.redis_host, self.config.redis_port))
            s.close()
            return CheckResult(name=self.name, passed=True, message="Redis port open", warning=False)
        except (socket.timeout, ConnectionRefusedError, OSError):
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message="Redis not detected (optional dependency)",
            )


class ApiGatewayHealth(BaseCheck):
    name = "API Gateway health"
    description = "Modular API gateway /health endpoint"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.modular_api_url}/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            passed = isinstance(data, dict) and data.get("status") in ("healthy", "ok", True)
            return CheckResult(
                name=self.name, passed=passed,
                message=f"Gateway responded: {data.get('status', 'unknown')}",
                detail=data,
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Gateway unreachable: {e}")


class FrontendAvailability(BaseCheck):
    name = "Frontend availability"
    description = "Frontend dev server is serving content"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.frontend_url}/"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
            has_html = "<html" in body.lower() or "<!doctype html" in body.lower()
            passed = status == 200 and has_html
            return CheckResult(
                name=self.name, passed=passed,
                message=f"HTTP {status}, {'has HTML' if has_html else 'unexpected content'}",
                detail={"status_code": status, "content_length": len(body)},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Frontend unreachable: {e}")
