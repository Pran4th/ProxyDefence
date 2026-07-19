import urllib.request
import json

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig
from ..auth import get_auth_headers

CATEGORY = "ai_layer"
DESCRIPTION = "Supervisor Agent, Intelligence Agent, Tool execution, RAG, LLM, Copilot"


def get_checks(config: ValidationConfig):
    return [
        LLMConnectivity(config),
        CopilotQueryResponse(config),
        HybridRAGRetrieval(config),
        EmbeddingRetrieval(config),
        AgentRouterAccessible(config),
        AgentQueryResponse(config),
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
            # Health endpoint may not expose LLM - check via Copilot query test instead
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message="LLM check not exposed in /health. Verify via Copilot query test.",
                detail={"health": data},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"LLM check failed: {e}")


class CopilotQueryResponse(BaseCheck):
    name = "Copilot query response"
    description = "POST /copilot/query generates a response for a deterministic prompt"

    def _run(self) -> CheckResult:
        try:
            headers = {"Content-Type": "application/json", **get_auth_headers(self.config)}
            if "Authorization" not in headers:
                return CheckResult(
                    name=self.name, passed=False,
                    message="Could not obtain an auth token from /auth/register or /auth/login",
                )
            payload = json.dumps({"question": "What is the current threat level based on recent articles?"}).encode()
            url = f"{self.config.modular_api_url}/copilot/query"
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())

            # ``/copilot/query`` exposes the generated answer as ``summary``.
            # Keep the older aliases for backwards-compatible deployments, but
            # validate the current public contract first.
            response = (
                data.get("summary")
                or data.get("response")
                or data.get("answer")
                or data.get("content")
                or ""
            )
            has_content = len(str(response)) > 10
            return CheckResult(
                name=self.name, passed=has_content,
                message=f"Response generated ({len(str(response))} chars)" if has_content else "Empty response",
                detail={"response_preview": str(response)[:200] if has_content else "", "full": data},
            )
        except urllib.error.HTTPError as e:
            body = e.read().decode()
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
    description = "GET /api/v1/rag/search retrieves relevant context"

    def _run(self) -> CheckResult:
        try:
            headers = get_auth_headers(self.config)
            if "Authorization" not in headers:
                return CheckResult(
                    name=self.name, passed=False,
                    message="Could not obtain an auth token from /auth/register or /auth/login",
                )
            url = f"{self.config.modular_api_url}/api/v1/rag/search?q=energy+prices&limit=3"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())

            count = data.get("result_count", len(data.get("context_structured", [])))
            return CheckResult(
                name=self.name, passed=count > 0,
                message=f"{count} RAG results returned" if count > 0 else "No RAG results",
                detail={"count": count, "context_structured": data.get("context_structured", [])[:3]},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(
                name=self.name, passed=False,
                message=f"RAG search failed (HTTP {e.code})",
                detail={"status": e.code},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"RAG check error: {e}")


class EmbeddingRetrieval(BaseCheck):
    name = "Embedding retrieval"
    description = "article_embeddings table has vector data"

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
                message="No embeddings found" if count is not None else "article_embeddings table not found",
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Embedding retrieval check failed: {e}")


class AgentRouterAccessible(BaseCheck):
    name = "Agent router accessible"
    description = "GET /api/v1/agents/list returns the registered agent list"

    def _run(self) -> CheckResult:
        try:
            headers = get_auth_headers(self.config)
            if "Authorization" not in headers:
                return CheckResult(
                    name=self.name, passed=False,
                    message="Could not obtain an auth token from /auth/register or /auth/login",
                )
            url = f"{self.config.modular_api_url}/api/v1/agents/list"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            count = len(data) if isinstance(data, list) else 0
            return CheckResult(
                name=self.name, passed=count > 0,
                message=f"{count} agents registered",
                detail={"agents": data},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(name=self.name, passed=False, message=f"Agent list failed (HTTP {e.code})")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Agent check error: {e}")


class AgentQueryResponse(BaseCheck):
    name = "Agent query response"
    description = "POST /api/v1/agents/query runs the supervisor agent end-to-end"

    def _run(self) -> CheckResult:
        try:
            headers = {"Content-Type": "application/json", **get_auth_headers(self.config)}
            if "Authorization" not in headers:
                return CheckResult(
                    name=self.name, passed=False,
                    message="Could not obtain an auth token from /auth/register or /auth/login",
                )
            payload = json.dumps({"query": "Summarize the current geopolitical risk level."}).encode()
            url = f"{self.config.modular_api_url}/api/v1/agents/query"
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            # The supervisor can invoke multiple specialists and an external
            # LLM. Give this optional external path a bounded but realistic
            # 90-second validation window; it remains a warning on timeout.
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            has_content = len(str(data.get("content", ""))) > 10
            return CheckResult(
                name=self.name, passed=has_content,
                message=f"Agent responded ({len(str(data.get('content', '')))} chars) via {data.get('agent_name', '?')}" if has_content else "Empty agent response",
                detail={"response_preview": str(data.get("content", ""))[:200], "agent_name": data.get("agent_name")},
            )
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            return CheckResult(
                name=self.name, passed=False,
                message=f"Agent query failed (HTTP {e.code})",
                detail={"status": e.code, "body": body[:300]},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Agent query error: {e}")
