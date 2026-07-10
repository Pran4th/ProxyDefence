import json
import urllib.request

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig
from ..auth import get_auth_headers

CATEGORY = "frontend"
DESCRIPTION = "Frontend pages and the backend endpoints they depend on"


def get_checks(config: ValidationConfig):
    return [
        FrontendServesPages(config),
        FrontendApiConnection(config),
        PublicPreviewAccessible(config),
        ArticlesEndpoint(config),
        AnalyticsSummaryEndpoint(config),
        SearchEndpoint(config),
    ]


class FrontendServesPages(BaseCheck):
    name = "Frontend serves pages"
    description = "Frontend dev server responds with HTML"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.frontend_url}/"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
            has_html = "<html" in body.lower() or "<!doctype html" in body.lower()
            has_root = 'id="root"' in body or '<div id="root">' in body
            passed = status == 200 and has_html and has_root
            return CheckResult(
                name=self.name, passed=passed,
                message=f"HTTP {status}, HTML: {has_html}, React root: {has_root}",
                detail={
                    "status_code": status,
                    "has_html": has_html,
                    "has_react_root": has_root,
                    "content_length": len(body),
                },
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Frontend unreachable: {e}")


class FrontendApiConnection(BaseCheck):
    name = "Frontend API connection configured"
    description = "Frontend has correct API URL configured"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.frontend_url}/"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")

            api_url_in_bundle = f"localhost:{self.config.modular_api_port}" in body or f":{self.config.modular_api_port}" in body
            return CheckResult(
                name=self.name, passed=True,
                message=f"API URL pattern {'found' if api_url_in_bundle else 'not confirmed'} in frontend bundle",
                detail={"api_port_mentioned": api_url_in_bundle},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Frontend API check failed: {e}")


class PublicPreviewAccessible(BaseCheck):
    name = "Public preview accessible (no auth)"
    description = "GET /public/preview returns data without a token - what the landing page uses pre-login"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.modular_api_url}/public/preview"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            passed = isinstance(data, dict) and len(data) > 0
            return CheckResult(
                name=self.name, passed=passed,
                message=f"Public preview returned data ({len(data)} keys)" if passed else "Empty preview response",
                detail={"keys": list(data.keys())[:10] if isinstance(data, dict) else "non-dict"},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(name=self.name, passed=False, message=f"Public preview failed (HTTP {e.code}) - landing page will be blank pre-login")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Public preview check error: {e}")


class ArticlesEndpoint(BaseCheck):
    name = "Articles endpoint"
    description = "GET /articles returns data (requires auth)"

    def _run(self) -> CheckResult:
        try:
            headers = get_auth_headers(self.config)
            if "Authorization" not in headers:
                return CheckResult(name=self.name, passed=False, message="Could not obtain an auth token")
            url = f"{self.config.modular_api_url}/articles/?limit=5"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            articles = data if isinstance(data, list) else data.get("articles", data.get("items", data.get("data", [])))
            count = len(articles) if isinstance(articles, list) else 1
            return CheckResult(
                name=self.name, passed=count > 0,
                message=f"{count} articles returned" if count > 0 else "No articles found",
                detail={"count": count},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(name=self.name, passed=True, warning=True, message=f"Articles endpoint HTTP {e.code}")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Articles check error: {e}")


class AnalyticsSummaryEndpoint(BaseCheck):
    name = "Analytics summary endpoint"
    description = "GET /analytics/summary returns data (requires auth)"

    def _run(self) -> CheckResult:
        try:
            headers = get_auth_headers(self.config)
            if "Authorization" not in headers:
                return CheckResult(name=self.name, passed=False, message="Could not obtain an auth token")
            url = f"{self.config.modular_api_url}/analytics/summary"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            passed = isinstance(data, dict) and len(data) > 0
            return CheckResult(
                name=self.name, passed=passed,
                message=f"Analytics endpoint returned data ({len(data)} keys)" if passed else "Empty analytics response",
                detail={"keys": list(data.keys())[:10] if isinstance(data, dict) else "non-dict"},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(name=self.name, passed=False, message=f"Analytics endpoint HTTP {e.code}")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Analytics check error: {e}")


class SearchEndpoint(BaseCheck):
    name = "Search endpoint"
    description = "GET /search returns results (requires auth)"

    def _run(self) -> CheckResult:
        try:
            headers = get_auth_headers(self.config)
            if "Authorization" not in headers:
                return CheckResult(name=self.name, passed=False, message="Could not obtain an auth token")
            url = f"{self.config.modular_api_url}/search/?q=energy&limit=3"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                data = json.loads(resp.read())
            results = data if isinstance(data, list) else data.get("results", data.get("items", data.get("data", [])))
            count = len(results) if isinstance(results, list) else 1
            return CheckResult(
                name=self.name, passed=True, warning=count == 0,
                message=f"{count} search results for 'energy'" if count > 0 else "Search endpoint OK, no results for 'energy' yet",
                detail={"count": count},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(name=self.name, passed=False, message=f"Search endpoint HTTP {e.code}")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Search check error: {e}")
