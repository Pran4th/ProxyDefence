import json
import time
from dataclasses import dataclass, field
from typing import Any

from .base_check import CheckResult


@dataclass
class ValidationReport:
    start_time: float = 0.0
    end_time: float = 0.0
    results: list[CheckResult] = field(default_factory=list)
    category_results: dict[str, list[CheckResult]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed and not r.warning)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed and not r.warning)

    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.warning)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "warnings": self.warnings,
                "duration_seconds": round(self.duration, 2),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.end_time)),
            },
            "categories": {
                cat: [r.to_dict() for r in results]
                for cat, results in sorted(self.category_results.items())
            },
        }

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def to_html(self, path: str) -> None:
        data = self.to_dict()
        rows_html = ""
        for cat, checks in data["categories"].items():
            cat_passed = sum(1 for c in checks if c["passed"] and not c["warning"])
            cat_failed = sum(1 for c in checks if not c["passed"] and not c["warning"])
            cat_warn = sum(1 for c in checks if c["warning"])
            badge = "pass" if cat_failed == 0 else "fail"
            rows_html += f"""<tr class="category"><td colspan="3"><strong>[{badge.upper()}] {cat}</strong> ({cat_passed} passed, {cat_failed} failed, {cat_warn} warnings)</td></tr>"""
            for c in checks:
                cls = "pass" if c["passed"] and not c["warning"] else "warn" if c["warning"] else "fail"
                icon = "PASS" if c["passed"] and not c["warning"] else "WARN" if c["warning"] else "FAIL"
                rows_html += f"""<tr class="{cls}"><td><span class="icon-{cls}">{icon}</span></td><td>{c['name']}</td><td>{c['message']}</td></tr>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ProxyDefence Validation Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #0d1117; color: #c9d1d9; }}
h1 {{ color: #58a6ff; }}
.summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }}
.card {{ padding: 16px; border-radius: 8px; text-align: center; }}
.card.pass {{ background: #1b3a2b; border: 1px solid #238636; }}
.card.fail {{ background: #3a1b1b; border: 1px solid #da3633; }}
.card.warn {{ background: #3a2f1b; border: 1px solid #d29922; }}
.card.total {{ background: #1b243a; border: 1px solid #58a6ff; }}
.card .num {{ font-size: 28px; font-weight: bold; }}
.card .label {{ font-size: 12px; opacity: 0.8; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #30363d; }}
th {{ background: #161b22; color: #8b949e; font-size: 12px; text-transform: uppercase; }}
.category td {{ background: #161b22; font-weight: bold; }}
.icon-pass {{ color: #3fb950; font-weight: bold; }}
.icon-fail {{ color: #f85149; font-weight: bold; }}
.icon-warn {{ color: #d29922; font-weight: bold; }}
tr.pass td {{ color: #3fb950; }}
tr.fail td {{ color: #f85149; }}
tr.warn td {{ color: #d29922; }}
</style>
</head>
<body>
<h1>ProxyDefence Validation Report</h1>
<p>Generated: {data["summary"]["timestamp"]} | Duration: {data["summary"]["duration_seconds"]}s</p>
<div class="summary">
<div class="card total"><div class="num">{data["summary"]["total"]}</div><div class="label">Total Checks</div></div>
<div class="card pass"><div class="num">{data["summary"]["passed"]}</div><div class="label">Passed</div></div>
<div class="card fail"><div class="num">{data["summary"]["failed"]}</div><div class="label">Failed</div></div>
<div class="card warn"><div class="num">{data["summary"]["warnings"]}</div><div class="label">Warnings</div></div>
</div>
<table><thead><tr><th style="width:60px"></th><th>Check</th><th>Message</th></tr></thead><tbody>{rows_html}</tbody></table>
</body>
</html>"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def print_terminal(self) -> None:
        print(f"\n{'='*60}")
        print(f"  ProxyDefence Validation Report")
        print(f"  Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(self.end_time))}")
        print(f"  Duration: {self.duration:.2f}s")
        print(f"{'='*60}")
        print(f"  Total: {self.total}  |  [PASS] {self.passed}  |  [FAIL] {self.failed}  |  [WARN] {self.warnings}")
        print(f"{'='*60}")

        for cat, checks in self.category_results.items():
            cat_passed = sum(1 for r in checks if r.passed and not r.warning)
            cat_failed = sum(1 for r in checks if not r.passed and not r.warning)
            cat_warn = sum(1 for r in checks if r.warning)
            icon = "[OK]" if cat_failed == 0 else "[!!]"
            print(f"\n  {icon} {cat}  ({cat_passed} passed, {cat_failed} failed, {cat_warn} warnings)")
            print(f"  {'-'*56}")
            for r in checks:
                status = "[PASS]" if r.passed and not r.warning else "[WARN]" if r.warning else "[FAIL]"
                print(f"    {status} {r.name:<50} {r.duration_ms:>6.0f}ms")
                if not r.passed or r.warning:
                    print(f"       {r.message}")
