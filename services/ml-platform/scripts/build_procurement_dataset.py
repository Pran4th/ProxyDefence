"""Builds the procurement-options training dataset by fusing:
  - energy.suppliers + energy.supplier_intelligence (Postgres, seeded by energy-service)
  - REAL OFAC sanctions counts per supplier country   (datasets/processed/ofac-sanctions)
  - REAL GDELT escalation rates per supplier country  (datasets/processed/gdelt-merged)
  - REAL port tanker-traffic congestion per country   (datasets/processed/world-port-index)

Label design (explicit, testable assumptions — see OUTCOME MODEL below):
  outcome_score simulates realized delivery performance for a procurement option.
  It starts from the same composite formula the live ProcurementOptimizer uses
  (cost 35% / risk 30% / lead-time 20% / strategic 15%) and adds stochastic
  execution noise whose variance grows with sanctions exposure, geopolitical
  escalation, and port congestion. A model trained on this predicts EXPECTED
  outcome, so ranking by prediction = risk-adjusted supplier ranking.

Also (--enrich): writes real sanctions/escalation signals back into
energy.supplier_intelligence so the live optimizer stops using formula defaults.

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/build_procurement_dataset.py [--enrich]
"""
from __future__ import annotations

import ast
import asyncio
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from backend.shared.settings import settings  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED = REPO_ROOT / "datasets" / "processed"
OUT_DIR = PROCESSED / "procurement"
OUT_PATH = OUT_DIR / "procurement-options.csv"

N_SCENARIOS = 400
SEED = 42

# Supplier slug -> (ISO3 country, OFAC program keyword, Brent-relative cost offset $/bbl)
SUPPLIER_COUNTRY = {
    "saudi-aramco-supplier": ("SAU", None, 0.0),
    "rosneft-supplier": ("RUS", "RUSSIA", -12.0),   # Urals discount
    "adnoc-supplier": ("ARE", None, -0.5),
    "sinopec-supplier": ("CHN", "CHINA", 1.5),
    "exxonmobil-supplier": ("USA", None, 2.0),
    "shell-supplier": ("GBR", None, 2.0),
    "bp-supplier": ("GBR", None, 1.8),
    "petrobras-supplier": ("BRA", None, -1.0),
    "equinor-supplier": ("NOR", None, 1.0),
}

BRENT_BASE = 82.0  # $/bbl anchor for scenario generation


def _latest(dirpath: Path, pattern: str) -> Path:
    candidates = sorted(dirpath.rglob(pattern))
    if not candidates:
        raise FileNotFoundError(f"no {pattern} under {dirpath}")
    return candidates[-1]


def load_sanction_counts() -> dict[str, int]:
    path = _latest(PROCESSED / "ofac-sanctions", "ofac-sanctions.csv")
    df = pd.read_csv(path)
    programs = df["attributes"].apply(lambda s: str(ast.literal_eval(s).get("program", "")))
    counts: dict[str, int] = {}
    for iso3, keyword, _ in SUPPLIER_COUNTRY.values():
        if keyword is None:
            counts.setdefault(iso3, 0)
        else:
            counts[iso3] = int(programs.str.contains(keyword, case=False, na=False).sum())
    return counts


def load_gdelt_escalation() -> dict[str, float]:
    path = PROCESSED / "gdelt-merged" / "gdelt-events-sample.csv"
    df = pd.read_csv(path)
    attrs = df["attributes"].apply(ast.literal_eval)
    frame = pd.DataFrame({
        "country": attrs.apply(lambda d: d.get("action_geo_country") or d.get("actor1_country") or "NONE"),
        "escalation": ((attrs.apply(lambda d: d.get("quad_class")) == 4)
                       | (attrs.apply(lambda d: d.get("goldstein_scale")) <= -5)).astype(int),
    })
    # GDELT action_geo_country is FIPS 2-letter; actor country is ISO3 — normalize what we need
    fips_to_iso3 = {"SA": "SAU", "RS": "RUS", "AE": "ARE", "CH": "CHN", "US": "USA",
                    "UK": "GBR", "BR": "BRA", "NO": "NOR"}
    frame["country"] = frame["country"].map(lambda c: fips_to_iso3.get(c, c))
    grouped = frame.groupby("country")["escalation"].agg(["mean", "count"])
    global_rate = float(frame["escalation"].mean())
    rates: dict[str, float] = {}
    for iso3, _, _ in SUPPLIER_COUNTRY.values():
        if iso3 in grouped.index and grouped.loc[iso3, "count"] >= 50:
            rates[iso3] = float(grouped.loc[iso3, "mean"])
        else:
            rates[iso3] = global_rate
    return rates


def load_port_congestion() -> dict[str, float]:
    path = _latest(PROCESSED / "world-port-index", "world-port-index.csv")
    df = pd.read_csv(path)
    attrs = df["attributes"].apply(ast.literal_eval)
    frame = pd.DataFrame({
        "iso3": attrs.apply(lambda d: d.get("country_code")),
        "tanker": attrs.apply(lambda d: d.get("vessel_count_tanker") or 0.0),
        "total": attrs.apply(lambda d: d.get("vessel_count_total") or 0.0),
    })
    grouped = frame.groupby("iso3").agg(tanker=("tanker", "sum"), total=("total", "sum"))
    # congestion proxy: country tanker traffic normalized to the busiest tanker country
    max_tanker = grouped["tanker"].max()
    out: dict[str, float] = {}
    for iso3, _, _ in SUPPLIER_COUNTRY.values():
        if iso3 in grouped.index and max_tanker > 0:
            out[iso3] = float(grouped.loc[iso3, "tanker"] / max_tanker)
        else:
            out[iso3] = 0.1
    return out


async def load_suppliers(pool: asyncpg.Pool) -> pd.DataFrame:
    rows = await pool.fetch(
        """SELECT s.slug, s.name, s.supplier_type, s.criticality,
                  si.reliability_score, si.avg_lead_time_days, si.on_time_delivery_pct,
                  si.strategic_value, si.country_political_stability
           FROM energy.suppliers s
           JOIN energy.supplier_intelligence si ON si.supplier_uuid = s.uuid
           WHERE s.is_deleted = false"""
    )
    return pd.DataFrame([dict(r) for r in rows])


def build_options(suppliers: pd.DataFrame, sanctions: dict[str, int],
                  escalation: dict[str, float], congestion: dict[str, float]) -> pd.DataFrame:
    rng = np.random.RandomState(SEED)
    rows = []
    for run_id in range(N_SCENARIOS):
        brent = BRENT_BASE + rng.normal(0, 8)  # market regime per scenario
        for _, s in suppliers.iterrows():
            iso3, _, offset = SUPPLIER_COUNTRY.get(s["slug"], ("UNK", None, 0.0))
            sanction_count = sanctions.get(iso3, 0)
            esc_rate = escalation.get(iso3, 0.19)
            congest = congestion.get(iso3, 0.1)

            sanction_norm = min(sanction_count / 5000.0, 1.0)
            cost_bbl = brent + offset + rng.normal(0, 1.5)
            lead_time = float(s["avg_lead_time_days"]) + rng.normal(0, 2)
            rel = float(s["reliability_score"])
            stability = float(s["country_political_stability"]) * (1 - 0.4 * sanction_norm) * (1 - 0.5 * esc_rate)
            on_time = float(s["on_time_delivery_pct"]) / 100.0
            strategic = float(s["strategic_value"])

            # same shape as ProcurementOptimizer._build_option
            risk_score = 1.0 - (rel * 0.5 + stability * 0.3 + on_time * 0.2)
            lead_time_score = max(0.0, 1.0 - (lead_time - 5) / 55.0)
            cost_score = max(0.0, 1.0 - (cost_bbl - 50) / 100.0)
            composite = (cost_score * 0.35 + (1 - risk_score) * 0.30
                         + lead_time_score * 0.20 + strategic * 0.15)

            # OUTCOME MODEL: execution noise scales with real risk signals.
            # sd ranges 0.02 (clean supplier) .. ~0.10 (sanctioned + escalating + congested)
            noise_sd = 0.02 + 0.05 * sanction_norm + 0.15 * esc_rate + 0.02 * congest
            outcome = composite + rng.normal(0, noise_sd) - 0.08 * sanction_norm * rng.binomial(1, esc_rate)

            rows.append({
                "run_id": run_id,
                "supplier_slug": s["slug"],
                "supplier_type": s["supplier_type"],
                "cost_bbl": round(cost_bbl, 2),
                "lead_time_days": round(lead_time, 1),
                "reliability_score": rel,
                "on_time_delivery_pct": on_time,
                "strategic_value": strategic,
                "country_stability_base": float(s["country_political_stability"]),
                "sanction_count": sanction_count,
                "gdelt_escalation_rate": round(esc_rate, 4),
                "port_congestion_index": round(congest, 4),
                "brent_anchor": round(brent, 2),
                "outcome_score": round(float(np.clip(outcome, 0, 1)), 4),
            })
    return pd.DataFrame(rows)


async def enrich_supplier_intelligence(pool: asyncpg.Pool, sanctions: dict[str, int],
                                       escalation: dict[str, float]) -> None:
    suppliers = await pool.fetch(
        "SELECT s.uuid, s.slug FROM energy.suppliers s WHERE s.is_deleted = false"
    )
    for s in suppliers:
        iso3, _, _ = SUPPLIER_COUNTRY.get(s["slug"], ("UNK", None, 0.0))
        sanction_count = sanctions.get(iso3, 0)
        esc_rate = escalation.get(iso3, 0.19)
        sanctioned = sanction_count > 100
        compliance = "high" if sanctioned else ("medium" if esc_rate > 0.25 else "low")
        result = await pool.execute(
            """UPDATE energy.supplier_intelligence si
               SET sanctions_exposure = $2,
                   compliance_risk = $3,
                   country_political_stability = GREATEST(0.05,
                       country_political_stability * (1 - 0.4 * LEAST($4::float / 5000.0, 1.0)) * (1 - 0.5 * $5::float))
               FROM energy.suppliers s
               WHERE s.uuid = si.supplier_uuid AND s.slug = $1""",
            s["slug"], sanctioned, compliance, float(sanction_count), esc_rate,
        )
        print(f"  enriched {s['slug']}: sanctions={sanction_count} exposure={sanctioned} "
              f"escalation={esc_rate:.3f} compliance={compliance} ({result})")


async def main() -> None:
    enrich = "--enrich" in sys.argv

    print("loading real signals...")
    sanctions = load_sanction_counts()
    escalation = load_gdelt_escalation()
    congestion = load_port_congestion()
    print(f"  sanctions by country: {sanctions}")
    print(f"  gdelt escalation rates: { {k: round(v, 3) for k, v in escalation.items()} }")
    print(f"  port congestion index: { {k: round(v, 3) for k, v in congestion.items()} }")

    host = settings.POSTGRES_HOST if settings.POSTGRES_HOST != "postgres" else "localhost"
    pool = await asyncpg.create_pool(
        host=host, port=settings.POSTGRES_PORT, user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD, database=settings.POSTGRES_DB,
        min_size=1, max_size=2,
    )

    suppliers = await load_suppliers(pool)
    print(f"suppliers loaded: {len(suppliers)}")

    options = build_options(suppliers, sanctions, escalation, congestion)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    options.to_csv(OUT_PATH, index=False)
    print(f"wrote {len(options)} option rows -> {OUT_PATH}")

    if enrich:
        print("enriching energy.supplier_intelligence with real signals...")
        await enrich_supplier_intelligence(pool, sanctions, escalation)

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
