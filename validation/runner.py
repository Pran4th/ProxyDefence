#!/usr/bin/env python3
"""ProxyDefence End-to-End Validation Framework.

Usage:
    python -m validation.runner                    # all checks
    python -m validation.runner --category infra    # specific category
    python -m validation.runner --list              # list check categories
"""

import argparse
import importlib
import pkgutil
import time
import sys
from typing import Any

from .config import ValidationConfig
from .report import ValidationReport


def discover_checks():
    """Discover all check modules in validation.checks package."""
    import validation.checks as pkg

    categories = {}
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_"):
            continue
        module = importlib.import_module(f"validation.checks.{modname}")
        if hasattr(module, "CATEGORY") and hasattr(module, "get_checks"):
            categories[module.CATEGORY] = module
    return categories


def run_category(module, config) -> list[Any]:
    checks = module.get_checks(config)
    results = []
    for check in checks:
        result = check.run()
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description="ProxyDefence Validation Framework")
    parser.add_argument("--category", "-c", help="Run only a specific category")
    parser.add_argument("--list", "-l", action="store_true", help="List available categories")
    parser.add_argument("--output", "-o", default="validation_report", help="Report output path prefix")
    args = parser.parse_args()

    config = ValidationConfig()
    categories = discover_checks()

    if args.list:
        print("Available validation categories:")
        for name, mod in sorted(categories.items()):
            desc = getattr(mod, "DESCRIPTION", "")
            print(f"  {name:<30} {desc}")
        return

    if args.category:
        if args.category not in categories:
            print(f"Unknown category: {args.category}")
            print(f"Available: {', '.join(sorted(categories.keys()))}")
            sys.exit(1)
        selected = {args.category: categories[args.category]}
    else:
        selected = categories

    report = ValidationReport()
    report.start_time = time.time()

    for cat_name, module in sorted(selected.items()):
        cat_results = run_category(module, config)
        report.results.extend(cat_results)
        report.category_results[cat_name] = cat_results

    report.end_time = time.time()

    report.print_terminal()

    json_path = f"{args.output}.json"
    html_path = f"{args.output}.html"
    report.to_json(json_path)
    report.to_html(html_path)
    print(f"\n  Reports written to:")
    print(f"    JSON: {json_path}")
    print(f"    HTML: {html_path}")
    print()

    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
