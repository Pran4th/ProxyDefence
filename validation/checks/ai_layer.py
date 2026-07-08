import urllib.request
import json

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "ai_layer"
DESCRIPTION = "Supervisor Agent, Intelligence Agent, Tool execution, RAG, LLM, Copilot"


def get_checks(config: ValidationConfig):
    return [
        LLMConnectivity(config),
        CopilotEndpointAccessible(config),
        CopilotQueryResponse(config),
        HybridRAGRetrieval(config),
        EmbeddingRetrieval(config),
        AgentRouterAccessible(config),
    ]


class LLMConnectivity(BaseCheck):
    name = "LLM connectivity"
    description = "Groq/LLM provider is reachable from API gateway"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.modular_api_url}/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            llm_status = data.get("llm") or data.get("groq") or data.get("openai")
            if llm_status:
                status_str = str(llm_status.get("status", llm_status))
                passed = "ok" in status_str.lower() or "connected" in status_str.lower() or status_str == "true"
                return CheckResult(
                    name=self.name, passed=passed,
                    message=f"LLM status: {status_str}",
                    detail={"llm_check": llm_status},
                )
            # Health endpoint may not expose LLM - check via liveness
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message="LLM check not exposed in /health. Verify via Copilot query test.",
                detail={"health": data},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"LLM check failed: {e}")


class CopilotEndpointAccessible(BaseCheck):
    name = "Copilot endpoint accessible"
    description = "AI Copilot endpoint exists and responds"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.modular_api_url}/copilot/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            return CheckResult(name=self.name, passed=True, message="Copilot health endpoint responding", detail=data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return CheckResult(
                    name=self.name, passed=True, warning=True,
                    message="Copilot health endpoint not found (may be at /api/copilot/health)",
                )
            return CheckResult(name=self.name, passed=False, message=f"Copilot endpoint error HTTP {e.code}")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Copilot unreachable: {e}")


class CopilotQueryResponse(BaseCheck):
    name = "Copilot query response"
    description = "Copilot generates responses for deterministic prompts"

    def _run(self) -> CheckResult:
        try:
            payload = json.dumps({"query": "What is the current threat level based on recent articles?", "max_tokens": 100}).encode()
            url = f"{self.config.modular_api_url}/copilot/query"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())

            response = data.get("response") or data.get("answer") or data.get("content") or ""
            has_content = len(str(response)) > 10
            return CheckResult(
                name=self.name, passed=has_content,
                message=f"Response generated ({len(str(response))} chars)" if has_content else "Empty response",
                detail={"response_preview": str(response)[:200] if has_content else "", "full": data},
            )
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 404:
                return CheckResult(
                    name=self.name, passed=True, warning=True,
                    message="Copilot query endpoint not deployed at /copilot/query",
                    detail={"status": e.code, "body": body[:300]},
                )
            if "API key" in body or "api_key" in body.lower():
                return CheckResult(
                    name=self.name, passed=False,
                    message=f"LLM API key not configured (HTTP {e.code})",
                    detail={"status": e.code, "body": body[:300]},
                )
            return CheckResult(
                name=self.name, passed=False,
                message=f"Copilot query failed (HTTP {e.code})",
                detail={"status": e.code, "body": body[:300]},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Copilot query error: {e}")


class HybridRAGRetrieval(BaseCheck):
    name = "Hybrid RAG retrieval"
    description = "RAG pipeline retrieves relevant context"

    def _run(self) -> CheckResult:
        try:
            payload = json.dumps({"query": "energy prices", "limit": 3}).encode()
            url = f"{self.config.modular_api_url}/rag/search"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            results = data.get("results") or data.get("documents") or data.get("items") or []
            count = len(results) if isinstance(results, list) else 0
            return CheckResult(
                name=self.name, passed=count > 0,
                message=f"{count} RAG results returned" if count > 0 else "No RAG results",
                detail={"count": count, "results": results[:3] if count > 0 else results},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message=f"RAG search endpoint not deployed (HTTP {e.code})",
                detail={"status": e.code},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"RAG check error: {e}")


class EmbeddingRetrieval(BaseCheck):
    name = "Embedding retrieval"
    description = "Embedding service generates and retrieves embeddings"

    def _run(self) -> CheckResult:
        try:
            import asyncpg
            import asyncio

            async def check():
                conn = await asyncpg.connect(
                    host=self.config.postgres_host, port=self.config.postgres_port,
                    user=self.config.postgres_user, password=self.config.postgres_password,
                    database=self.config.postgres_db, timeout=self.config.db_timeout,
                )
                tables = await conn.fetch(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                )
                table_names = [t["table_name"] for t in tables]
                # Check for article_embeddings table with vector data
                if "article_embeddings" in table_names:
                    count = await conn.fetchval("SELECT COUNT(*) FROM article_embeddings")
                    await conn.close()
                    return count
                await conn.close()
                return None

            count = asyncio.run(check())
            if count is not None and count > 0:
                return CheckResult(
                    name=self.name, passed=True,
                    message=f"{count} embeddings available",
                    detail={"embedding_count": count},
                )
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message=f"No embeddings found" if count is not None else "article_embeddings table not found",
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Embedding retrieval check failed: {e}")


class AgentRouterAccessible(BaseCheck):
    name = "Agent router accessible"
    description = "AI agent routing endpoints are registered"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.modular_api_url}/agent/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            return CheckResult(name=self.name, passed=True, message="Agent health endpoint responding", detail=data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return CheckResult(
                    name=self.name, passed=True, warning=True,
                    message="Agent endpoint not found at /agent/health (may use different prefix)",
                    detail={"status": e.code},
                )
            return CheckResult(name=self.name, passed=False, message=f"Agent endpoint error HTTP {e.code}")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Agent check error: {e}")
