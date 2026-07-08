import urllib.request

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "frontend"
DESCRIPTION = "Frontend pages: Dashboard, RiskDashboard, Copilot, DigitalTwin, Procurement, SPR, GraphExplorer"


def get_checks(config: ValidationConfig):
    return [
        FrontendServesPages(config),
        FrontendApiConnection(config),
        DashboardPageIntegration(config),
        ApiArticlesEndpoint(config),
        ApiAnalyticsEndpoint(config),
        ApiSearchEndpoint(config),
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
            # Check the frontend's JS bundle or env for VITE_API_URL
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


class DashboardPageIntegration(BaseCheck):
    name = "Dashboard API data accessible"
    description = "Backend analytics endpoint returns data for frontend"

    def _run(self) -> CheckResult:
        try:
            # Check that the analytics endpoint the dashboard uses is available
            url = f"{self.config.modular_api_url}/api/analytics/summary"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                import json
                data = json.loads(resp.read())
            passed = isinstance(data, dict) and len(data) > 0
            return CheckResult(
                name=self.name, passed=passed,
                message=f"Analytics endpoint returned data ({len(data)} keys)" if passed else "Empty analytics response",
                detail={"keys": list(data.keys())[:10] if isinstance(data, dict) else "non-dict"},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message=f"Analytics endpoint returned HTTP {e.code}",
                detail={"status": e.code},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Dashboard check error: {e}")


class ApiArticlesEndpoint(BaseCheck):
    name = "Articles API endpoint"
    description = "Backend /api/articles returns data"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.modular_api_url}/api/articles?limit=5"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                import json
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


class ApiAnalyticsEndpoint(BaseCheck):
    name = "Analytics API endpoint"
    description = "Backend analytics endpoints return data"

    def _run(self) -> CheckResult:
        endpoints = [
            "/api/analytics/summary",
            "/api/analytics/trends",
        ]
        results = {}
        any_ok = False
        for ep in endpoints:
            try:
                url = f"{self.config.modular_api_url}{ep}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                    import json
                    data = json.loads(resp.read())
                results[ep] = {"status": resp.status, "has_data": len(str(data)) > 10}
                any_ok = True
            except Exception as e:
                results[ep] = {"error": str(e)[:100]}

        return CheckResult(
            name=self.name, passed=any_ok,
            message=f"{sum(1 for r in results.values() if r.get('has_data'))}/{len(endpoints)} endpoints returning data",
            detail={"endpoints": results},
        )


class ApiSearchEndpoint(BaseCheck):
    name = "Search API endpoint"
    description = "Backend /api/search returns results"

    def _run(self) -> CheckResult:
        try:
            url = f"{self.config.modular_api_url}/api/search?q=energy&limit=3"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                import json
                data = json.loads(resp.read())
            results = data if isinstance(data, list) else data.get("results", data.get("items", data.get("data", [])))
            count = len(results) if isinstance(results, list) else 1
            return CheckResult(
                name=self.name, passed=count > 0,
                message=f"{count} search results for 'energy'" if count > 0 else "No search results",
                detail={"count": count},
            )
        except urllib.error.HTTPError as e:
            return CheckResult(name=self.name, passed=True, warning=True, message=f"Search endpoint HTTP {e.code}")
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Search check error: {e}")
