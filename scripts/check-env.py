#!/usr/bin/env python3
"""Environment validation script for ProxyDefence development setup."""

import importlib
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


def check(step: str, status: str, detail: str = ""):
    icon = {"PASS": "[OK]", "FAIL": "[!!]", "WARN": "[..]"}
    msg = f"  {icon[status]} {step}"
    if detail:
        msg += f" \u2014 {detail}"
    print(msg)


def main():
    print("=== ProxyDefence Environment Check ===\n")
    all_pass = True

    # 1. Python version
    print("1. Python")
    py_ver = sys.version_info
    if py_ver.major >= 3 and py_ver.minor >= 10:
        check(f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}", PASS)
    else:
        check(f"Python {py_ver.major}.{py_ver.minor}", FAIL, "3.10+ required")
        all_pass = False

    # 2. .env file
    print("\n2. Environment File")
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        check(".env found", PASS)
    else:
        example = REPO_ROOT / ".env.example"
        if example.exists():
            check(".env missing", WARN, "Copy .env.example to .env")
        else:
            check(".env missing", FAIL)

    # 3. Docker
    print("\n3. Docker")
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            check(f"Docker running (v{result.stdout.strip()})", PASS)
        else:
            check("Docker not running", WARN, "Start Docker Desktop")
    except FileNotFoundError:
        check("Docker not found", WARN, "Install Docker Desktop")
    except subprocess.TimeoutExpired:
        check("Docker timeout", WARN)

    # 4. Docker Compose files
    print("\n4. Docker Compose Files")
    for fname in ["docker-compose.yml", "docker-compose.full.yml"]:
        fpath = REPO_ROOT / fname
        if fpath.exists():
            result = subprocess.run(
                ["docker", "compose", "-f", str(fpath), "config", "--quiet"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                check(f"{fname}", PASS, "valid")
            else:
                check(f"{fname}", FAIL, f"invalid: {result.stderr.strip()}")
                all_pass = False
        else:
            check(f"{fname}", FAIL, "not found")
            all_pass = False

    # 5. Infrastructure containers
    print("\n5. Infrastructure Containers")
    checks = [
        ("postgres-db", "PostgreSQL"),
        ("kafka", "Kafka"),
        ("elasticsearch", "Elasticsearch"),
    ]
    for container_name, label in checks:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name=^{container_name}$", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            check(f"{label}", PASS, "running")
        else:
            check(f"{label}", WARN, "not running (start infra first)")

    # 6. Virtual environments
    print("\n6. Virtual Environments")
    services = [
        "ingest-service", "ml-service", "embedding-service",
        "database-service", "energy-service", "ml-platform", "modular-api",
    ]
    for svc in services:
        svc_dir = REPO_ROOT / "services" / svc
        venv_dir = svc_dir / ".venv"
        req_file = svc_dir / "requirements.txt"
        if not svc_dir.exists():
            check(f"{svc}", WARN, "directory not found")
            continue
        if not req_file.exists():
            check(f"{svc}", WARN, "requirements.txt not found")
            continue
        if not venv_dir.exists():
            check(f"{svc}", WARN, ".venv not found")
            continue
        python_bin = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        if not python_bin.exists():
            check(f"{svc}", WARN, ".venv missing python")
            continue
        result = subprocess.run(
            [str(python_bin), "-c",
             "import importlib.metadata; importlib.metadata.requires('fastapi')"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            check(f"{svc}", PASS)
        else:
            check(f"{svc}", WARN, "dependencies not installed")

    # 7. Shared imports
    print("\n7. Shared Imports")
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from backend.shared.config import SERVICE_VERSION
        check("backend.shared.config", PASS, f"version={SERVICE_VERSION}")
    except Exception as e:
        check("backend.shared.config", FAIL, str(e))
        all_pass = False

    try:
        from backend.shared.logging_config import setup_structlog
        check("backend.shared.logging_config", PASS)
    except Exception as e:
        check("backend.shared.logging_config", FAIL, str(e))
        all_pass = False

    try:
        from backend.shared.db_pool import get_pg_pool
        check("backend.shared.db_pool", PASS)
    except Exception as e:
        check("backend.shared.db_pool", FAIL, str(e))
        all_pass = False

    # 8. Research isolation
    print("\n8. Research Isolation")
    research_req = REPO_ROOT / "research" / "requirements-research.txt"
    if research_req.exists():
        check("research/requirements-research.txt", PASS)
    else:
        check("research/requirements-research.txt", WARN, "not found")

    # 9. Scripts
    print("\n9. Development Scripts")
    script_dir = REPO_ROOT / "scripts"
    if script_dir.exists():
        check("scripts/", PASS)
    else:
        check("scripts/", WARN, "directory not found")

    # Summary
    print(f"\n{'='*40}")
    if all_pass:
        print("Result: ALL CHECKS PASSED")
    else:
        print("Result: SOME CHECKS FAILED \u2014 review warnings above")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
