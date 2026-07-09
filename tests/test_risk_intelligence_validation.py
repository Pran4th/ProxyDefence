"""Risk Intelligence Validation Suite — Sprint 1 Production Validation.

Tests are organized to be runnable against a running energy-service.
Uses httpx to hit the actual HTTP API and asyncpg to inspect database state.

Usage:
    $env:PYTHONPATH = "C:\\ProxyWars\\ProxyDefence"
    python tests/test_risk_intelligence_validation.py
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import asyncpg

API_BASE = os.getenv("ENERGY_SERVICE_URL", "http://localhost:8006")
DSN = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
    f"/{os.getenv('POSTGRES_DB', 'defenseintel')}"
)

PASS = 0
FAIL = 0
SKIP = 0


def ok(msg: str):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg: str, detail: str = ""):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg} {detail}")


def skip(msg: str):
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {msg}")


async def check_api(endpoint: str, method: str = "GET", body: dict | None = None,
                    expected_status: int = 200, label: str | None = None) -> dict | None:
    label = label or f"{method} {endpoint}"
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                resp = await client.get(f"{API_BASE}{endpoint}")
            elif method == "POST":
                resp = await client.post(f"{API_BASE}{endpoint}", json=body or {})
            elif method == "DELETE":
                resp = await client.delete(f"{API_BASE}{endpoint}")
            else:
                resp = await client.request(method, f"{API_BASE}{endpoint}", json=body)

        latency = (time.time() - t0) * 1000
        status_ok = resp.status_code == expected_status

        if status_ok:
            ok(f"{label} → {resp.status_code} ({latency:.0f}ms)")
        else:
            fail(f"{label} expected {expected_status} got {resp.status_code} ({latency:.0f}ms)",
                 f"body={resp.text[:200]}")

        if resp.status_code == 200:
            data = resp.json()
            return data
        return None
    except Exception as e:
        fail(label, f"connection error: {e}")
        return None


async def validate_schema():
    print(f"\n{'='*60}")
    print("DATABASE SCHEMA VALIDATION")
    print(f"{'='*60}")

    conn = await asyncpg.connect(DSN)

    # Check all 10 intelligence tables exist
    expected_tables = [
        "risk_factors", "risk_scores", "disruption_signals", "response_telemetry",
        "commodity_prices", "ais_positions", "sanctions", "port_congestion",
        "tanker_availability", "scenario_assumptions",
    ]
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='energy'"
    )
    existing = {r["table_name"] for r in rows}
    for t in expected_tables:
        if t in existing:
            ok(f"Table energy.{t} exists")
        else:
            fail(f"Table energy.{t} MISSING")

    # Check risk_factors columns
    cols = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='energy' AND table_name='risk_factors'"
    )
    col_names = {c["column_name"] for c in cols}
    for needed in {"id", "uuid", "name", "weight", "is_active", "created_at"}:
        if needed in col_names:
            ok(f"risk_factors.{needed} exists")
        else:
            fail(f"risk_factors.{needed} MISSING")

    # Check risk_scores columns
    cols = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='energy' AND table_name='risk_scores'"
    )
    col_names = {c["column_name"] for c in cols}
    for needed in {"id", "uuid", "entity_uuid", "entity_type", "dimension", "score", "confidence", "breakdown", "expires_at"}:
        if needed in col_names:
            ok(f"risk_scores.{needed} exists")
        else:
            fail(f"risk_scores.{needed} MISSING")

    # Check for duplicates in FK-free tables
    for table in ["risk_scores", "disruption_signals", "commodity_prices", "sanctions"]:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM energy.{table}")
        uuid_count = await conn.fetchval(f"SELECT COUNT(DISTINCT uuid) FROM energy.{table}")
        if count == uuid_count:
            ok(f"energy.{table}: {count} rows, no UUID duplicates")
        else:
            fail(f"energy.{table}: {count} rows, {count - uuid_count} UUID DUPLICATES")

    # Check null constraints
    for table, col in [("disruption_signals", "title"), ("disruption_signals", "source"),
                       ("risk_scores", "score"), ("commodity_prices", "price"),
                       ("sanctions", "country_code")]:
        nulls = await conn.fetchval(f"SELECT COUNT(*) FROM energy.{table} WHERE {col} IS NULL")
        if nulls == 0:
            ok(f"energy.{table}: no NULL {col}")
        else:
            fail(f"energy.{table}: {nulls} NULL {col} values")

    await conn.close()


async def validate_risk_factors():
    print(f"\n{'='*60}")
    print("RISK FACTORS VALIDATION")
    print(f"{'='*60}")

    # Built-in risk factors from risk_engine.py
    import importlib.util
    spec = importlib.util.spec_from_file_location("risk_engine",
        "C:\\ProxyWars\\ProxyDefence\\services\\energy-service\\services\\risk_engine.py")
    mod = importlib.util.module_from_spec(spec)
    # Mock external deps
    import types
    backend = types.ModuleType('backend')
    backend.shared = types.ModuleType('backend.shared')
    backend.shared.logging_config = types.ModuleType('backend.shared.logging_config')
    class Logger:
        @staticmethod
        def info(*a,**kw): pass
        @staticmethod
        def exception(*a,**kw): pass
        @staticmethod
        def error(*a,**kw): pass
        def debug(*a,**kw): pass
        def warning(*a,**kw): pass
    def get_logger(n): return Logger()
    backend.shared.logging_config.get_logger = get_logger
    sys.modules['backend'] = backend
    sys.modules['backend.shared'] = backend.shared
    sys.modules['backend.shared.logging_config'] = backend.shared.logging_config
    sys.modules['db'] = types.ModuleType('db')
    sys.modules['db'].get_pool = lambda: None
    spec.loader.exec_module(mod)
    RISK_FACTORS = mod.RISK_FACTORS
    ok(f"{len(RISK_FACTORS)} built-in risk factors defined")

    # Verify factor weights
    for f in RISK_FACTORS:
        if 0 < f.weight <= 2.0:
            ok(f"Risk factor '{f.name}' weight={f.weight}")
        else:
            fail(f"Risk factor '{f.name}' invalid weight={f.weight}")

    # Verify factor dimensions
    valid_dims = {"geopolitical", "operational", "economic", "environmental"}
    for f in RISK_FACTORS:
        if f.dimension in valid_dims:
            ok(f"Risk factor '{f.name}' dimension={f.dimension}")
        else:
            fail(f"Risk factor '{f.name}' invalid dimension={f.dimension}")


async def validate_ingestion():
    print(f"\n{'='*60}")
    print("DATA INGESTION VALIDATION")
    print(f"{'='*60}")

    # Run all ingestors via API
    result = await check_api("/api/v1/intelligence/ingest/all", "POST",
                              label="Trigger all ingestors")
    if result:
        for k, v in result.items():
            ok(f"Ingestor '{k}': {v['ingested']} records, {v['signals_generated']} signals")

    # Check database counts
    conn = await asyncpg.connect(DSN)
    for table in ["commodity_prices", "sanctions", "port_congestion", "tanker_availability", "disruption_signals"]:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM energy.{table}")
        if count > 0:
            ok(f"energy.{table}: {count} rows ingested")
        else:
            fail(f"energy.{table}: EMPTY — ingestion failed")
    await conn.close()


async def validate_risk_scoring():
    print(f"\n{'='*60}")
    print("RISK SCORING VALIDATION")
    print(f"{'='*60}")

    conn = await asyncpg.connect(DSN)

    # Get a port to score
    port = await conn.fetchrow("SELECT uuid, name FROM energy.ports LIMIT 1")
    if port:
        result = await check_api(f"/api/v1/intelligence/risk/entity/{port['uuid']}?entity_type=ports",
                                  label=f"Score entity {port['name']}")
        if result:
            scores = result.get("scores", {})
            if "overall" in scores:
                ok(f"Entity risk score computed: overall={scores['overall']:.3f}")
            else:
                fail("No overall score in response")

    # Check dashboard
    result = await check_api("/api/v1/intelligence/risk", label="Risk dashboard")
    if result:
        for key in ["total_active_signals", "high_severity_signals", "average_risk_score", "risk_by_dimension"]:
            if key in result:
                ok(f"Dashboard field '{key}' = {result[key]}")
            else:
                fail(f"Dashboard missing field '{key}'")

    # Check risk trends
    result = await check_api("/api/v1/intelligence/risk/trends", label="Risk trends")
    if result:
        ok(f"Risk trends: {result.get('total', 0)} records returned")

    # Score persistence
    score_count = await conn.fetchval("SELECT COUNT(*) FROM energy.risk_scores")
    if score_count > 0:
        ok(f"{score_count} risk scores persisted in database")
    else:
        fail("No risk scores in database")

    await conn.close()


async def validate_signals():
    print(f"\n{'='*60}")
    print("SIGNAL DETECTION VALIDATION")
    print(f"{'='*60}")

    # List signals
    result = await check_api("/api/v1/intelligence/signals", label="List signals")
    if result:
        ok(f"{result.get('total', 0)} total signals")

    # Filter by severity
    result = await check_api("/api/v1/intelligence/signals?severity=high", label="Filter by severity=high")
    if result:
        ok(f"Severity filter: {result.get('total', 0)} high-severity signals")

    # Filter by dimension
    result = await check_api("/api/v1/intelligence/signals?risk_dimension=geopolitical",
                              label="Filter by dimension=geopolitical")
    if result:
        ok(f"Dimension filter: {result.get('total', 0)} geopolitical signals")

    # Create a custom signal
    signal = {
        "title": "TEST: Simulated Hormuz disruption",
        "description": "Validation test signal for Sprint 1 validation",
        "source": "validation-suite",
        "severity": "critical",
        "risk_dimension": "geopolitical",
        "affected_regions": ["IR", "AE", "SA"],
        "affected_commodities": ["crude"],
        "confidence": 0.95,
        "ttl_hours": 1,
    }
    result = await check_api("/api/v1/intelligence/signals", "POST", signal,
                              expected_status=201, label="Create custom signal")
    if result:
        signal_uuid = result.get("uuid")
        if signal_uuid:
            ok(f"Signal created with UUID: {signal_uuid}")

            # Get signal detail
            detail = await check_api(f"/api/v1/intelligence/signals/{signal_uuid}",
                                      label="Get signal detail")
            if detail:
                if detail.get("title") == signal["title"]:
                    ok("Signal detail matches creation payload")
                else:
                    fail("Signal detail mismatch")

    # Risk factors list
    result = await check_api("/api/v1/intelligence/risk-factors", label="List risk factors")
    if result:
        ok(f"{result.get('total', 0)} risk factors available")


async def validate_scenarios():
    print(f"\n{'='*60}")
    print("SCENARIO EVALUATION VALIDATION")
    print(f"{'='*60}")

    scenario = {
        "name": "Hormuz Closure Test",
        "description": "Validation: Strait of Hormuz blocked for 2 weeks",
        "assumptions": {
            "chokepoint_blockage": 0.85,
            "regional_conflict": 0.6,
            "price_volatility": 0.7,
            "supply_shortage": 0.65,
        },
        "risk_dimensions": ["geopolitical", "operational", "economic", "environmental"],
    }
    result = await check_api("/api/v1/intelligence/scenarios/evaluate", "POST", scenario,
                              label="Evaluate scenario")
    if result:
        for key in ["risk_scores", "risk_level", "assessment"]:
            if key in result:
                ok(f"Scenario result has '{key}': {result[key]}")
            else:
                fail(f"Scenario result missing '{key}'")
        if "overall" in result.get("risk_scores", {}):
            overall = result["risk_scores"]["overall"]
            ok(f"Scenario overall risk: {overall:.3f} ({result.get('risk_level', 'N/A')})")

    # List scenarios
    result = await check_api("/api/v1/intelligence/scenarios", label="List scenarios")
    if result:
        ok(f"{result.get('total', 0)} saved scenarios")


async def validate_data_views():
    print(f"\n{'='*60}")
    print("DATA VIEW VALIDATION")
    print(f"{'='*60}")

    for endpoint, label in [
        ("/api/v1/intelligence/commodity-prices", "Commodity prices"),
        ("/api/v1/intelligence/port-congestion", "Port congestion"),
        ("/api/v1/intelligence/tanker-availability", "Tanker availability"),
        ("/api/v1/intelligence/sanctions", "Sanctions"),
    ]:
        result = await check_api(endpoint, label=label)
        if result:
            items = result.get("items", [])
            total = result.get("total", 0)
            if total > 0:
                ok(f"{label}: {total} total, {len(items)} in response")
            else:
                fail(f"{label}: 0 records — check ingestors")


async def validate_entity_risk_profile():
    print(f"\n{'='*60}")
    print("ENTITY RISK PROFILE VALIDATION")
    print(f"{'='*60}")

    conn = await asyncpg.connect(DSN)

    # Get an import corridor
    corridor = await conn.fetchrow(
        "SELECT uuid, name FROM energy.import_corridors LIMIT 1"
    )
    if corridor:
        result = await check_api(
            f"/api/v1/intelligence/entity/import_corridors/{corridor['uuid']}/risk-profile",
            label=f"Risk profile for {corridor['name']}"
        )
        if result:
            for key in ["entity", "risk_scores", "active_signals", "related_entity_risks"]:
                if key in result:
                    ok(f"Risk profile has '{key}'")
                else:
                    fail(f"Risk profile missing '{key}'")

    await conn.close()


async def validate_propagation():
    print(f"\n{'='*60}")
    print("RISK PROPAGATION VALIDATION")
    print(f"{'='*60}")

    conn = await asyncpg.connect(DSN)
    corridor = await conn.fetchrow(
        "SELECT uuid, name FROM energy.import_corridors LIMIT 1"
    )
    if corridor:
        result = await check_api("/api/v1/intelligence/propagate", "POST", {
            "entity_uuid": str(corridor["uuid"]),
            "entity_type": "import_corridors",
            "risk_score": 0.85,
        }, label=f"Propagate risk from {corridor['name']}")
        if result:
            ok(f"Risk propagated to {result.get('propagated_to', 0)} entities")

    propagation_map = await check_api("/api/v1/intelligence/propagation-map",
                                       label="Propagation map")
    if propagation_map:
        ok(f"{propagation_map.get('total_propagated', 0)} propagated, {propagation_map.get('total_sources', 0)} sources")

    await conn.close()


async def validate_health():
    print(f"\n{'='*60}")
    print("HEALTH CHECK VALIDATION")
    print(f"{'='*60}")

    health = await check_api("/health", label="Health endpoint")
    if health:
        components = health.get("checks", health)
        ok(f"Health checks available")

    liveness = await check_api("/liveness", label="Liveness")
    readiness = await check_api("/readiness", label="Readiness")

    if liveness:
        ok("Liveness check passed")
    if readiness:
        ok("Readiness check passed")


async def validate_kafka_topics():
    print(f"\n{'='*60}")
    print("KAFKA TOPIC VALIDATION")
    print(f"{'='*60}")
    from confluent_kafka.admin import AdminClient
    admin = AdminClient({"bootstrap.servers": "localhost:9092"})
    topics = admin.list_topics(timeout=5).topics
    expected = ["commodity_prices", "ais_signals", "sanctions_updates",
                "disruption_signals", "intelligence_alerts"]
    for topic in expected:
        if topic in topics:
            ok(f"Kafka topic '{topic}' exists ({topics[topic].partitions} partitions)")
        else:
            fail(f"Kafka topic '{topic}' MISSING")


async def run_all():
    ts = datetime.now(timezone.utc)
    print(f"\n{'#'*60}")
    print(f"# RISK INTELLIGENCE VALIDATION SUITE")
    print(f"# Started: {ts.isoformat()}")
    print(f"# API: {API_BASE}")
    print(f"{'#'*60}")

    await validate_schema()
    await validate_risk_factors()
    await validate_ingestion()
    await validate_risk_scoring()
    await validate_signals()
    await validate_scenarios()
    await validate_data_views()
    await validate_entity_risk_profile()
    await validate_propagation()
    await validate_health()
    await validate_kafka_topics()

    te = datetime.now(timezone.utc)
    duration = (te - ts).total_seconds()
    print(f"\n{'='*60}")
    print(f"VALIDATION COMPLETE")
    print(f"  Duration: {duration:.1f}s")
    print(f"  PASS: {PASS}")
    print(f"  FAIL: {FAIL}")
    print(f"  SKIP: {SKIP}")
    print(f"  Total: {PASS + FAIL + SKIP}")
    if FAIL > 0:
        print(f"\n  !! {FAIL} TESTS FAILED")
    else:
        print(f"\n  ** ALL TESTS PASSED **")
    print(f"{'='*60}")
    return FAIL == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)
