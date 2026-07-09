"""SPR drawdown schedule optimizer — linear programming decision support for the
Strategic Reserve Optimisation service.

Formulation (per disruption scenario, daily buckets over horizon T):
  decision vars per day t:
    d_t  = SPR drawdown (bpd)          — bounded by facility max_drawdown_rate
    s_t  = emergency spot purchases    — bounded by a ramp: rerouted/spot supply takes
                                          RAMP_DAYS to reach full availability
                                          (motivated by the ~47-day stabilisation gap
                                          for economies without response intelligence)
    u_t  = unmet demand (bpd)          — heavily penalised
  constraints:
    d_t + s_t + u_t >= gap_t                      (cover the import gap)
    sum_{t'<=t} d_t' <= inventory - strategic floor (never empty the reserve)
  objective (minimise):
    SPOT_PREMIUM * s_t + DRAWDOWN_COST * d_t + PENALTY * u_t

Assumptions are explicit constants below — tunable per scenario, testable.

Reads the Indian SPR facility from energy.spr_facilities (Postgres).
Writes the optimal schedule to datasets/processed/spr/ and prints a policy summary.

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/optimize_spr_drawdown.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from backend.shared.settings import settings  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "datasets" / "processed" / "spr"

# --- explicit model assumptions -------------------------------------------------
INDIA_IMPORTS_BPD = 4_600_000          # approx crude imports
STRATEGIC_FLOOR_PCT = 0.20             # never draw below 20% of current inventory
SPOT_RAMP_DAYS = 21                    # days until spot/rerouted supply reaches max
SPOT_MAX_SHARE = 0.85                  # spot can replace at most 85% of the gap at full ramp
DRAWDOWN_COST = 1.0                    # relative cost units per bbl
SPOT_PREMIUM = 3.0                     # spot costs ~3x drawing own reserve (crisis premium)
UNMET_PENALTY = 100.0                  # unmet demand is far worse than any procurement

SCENARIOS = {
    "hormuz_partial_closure": {"import_loss_pct": 0.40, "duration_days": 30},
    "hormuz_full_closure": {"import_loss_pct": 0.65, "duration_days": 21},
    "red_sea_suspension": {"import_loss_pct": 0.15, "duration_days": 45},
}
# ---------------------------------------------------------------------------------


async def load_india_spr() -> dict:
    host = settings.POSTGRES_HOST if settings.POSTGRES_HOST != "postgres" else "localhost"
    conn = await asyncpg.connect(
        host=host, port=settings.POSTGRES_PORT, user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD, database=settings.POSTGRES_DB,
    )
    row = await conn.fetchrow(
        """SELECT name, current_inventory_barrels, max_drawdown_rate_bpd, max_refill_rate_bpd
           FROM energy.spr_facilities WHERE country = 'India' LIMIT 1"""
    )
    await conn.close()
    if row is None:
        raise RuntimeError("Indian SPR facility not found in energy.spr_facilities")
    return dict(row)


def optimize_scenario(name: str, cfg: dict, spr: dict) -> pd.DataFrame:
    T = cfg["duration_days"]
    gap = INDIA_IMPORTS_BPD * cfg["import_loss_pct"]
    max_draw = float(spr["max_drawdown_rate_bpd"])
    drawable = float(spr["current_inventory_barrels"]) * (1 - STRATEGIC_FLOOR_PCT)

    # variable layout: [d_0..d_{T-1}, s_0..s_{T-1}, u_0..u_{T-1}]
    n = 3 * T
    c = np.concatenate([
        np.full(T, DRAWDOWN_COST),
        np.full(T, SPOT_PREMIUM),
        np.full(T, UNMET_PENALTY),
    ])

    # coverage: -(d_t + s_t + u_t) <= -gap
    A_ub = np.zeros((T + 1, n))
    b_ub = np.zeros(T + 1)
    for t in range(T):
        A_ub[t, t] = -1.0
        A_ub[t, T + t] = -1.0
        A_ub[t, 2 * T + t] = -1.0
        b_ub[t] = -gap
    # cumulative drawdown <= drawable inventory
    A_ub[T, :T] = 1.0
    b_ub[T] = drawable

    bounds = []
    for t in range(T):
        bounds.append((0, max_draw))                                   # d_t
    for t in range(T):
        ramp = min(1.0, (t + 1) / SPOT_RAMP_DAYS)
        bounds.append((0, gap * SPOT_MAX_SHARE * ramp))                # s_t
    for t in range(T):
        bounds.append((0, None))                                       # u_t

    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"LP failed for {name}: {res.message}")

    d, s, u = res.x[:T], res.x[T:2 * T], res.x[2 * T:]
    return pd.DataFrame({
        "scenario": name,
        "day": np.arange(1, T + 1),
        "supply_gap_bpd": gap,
        "spr_drawdown_bpd": d.round(0),
        "spot_purchases_bpd": s.round(0),
        "unmet_demand_bpd": u.round(0),
        "cumulative_drawdown_bbl": d.cumsum().round(0),
        "remaining_inventory_bbl": (float(spr["current_inventory_barrels"]) - d.cumsum()).round(0),
    })


async def main() -> None:
    spr = await load_india_spr()
    inv = spr["current_inventory_barrels"]
    print(f"facility: {spr['name']}")
    print(f"  inventory: {inv / 1e6:.1f}M bbl | max drawdown: {spr['max_drawdown_rate_bpd']:,} bpd")
    print(f"  naive days-of-cover at full imports: {inv / INDIA_IMPORTS_BPD:.1f} days\n")

    frames = []
    for name, cfg in SCENARIOS.items():
        df = optimize_scenario(name, cfg, spr)
        frames.append(df)
        total_gap = df["supply_gap_bpd"].sum()
        covered_spr = df["spr_drawdown_bpd"].sum()
        covered_spot = df["spot_purchases_bpd"].sum()
        unmet = df["unmet_demand_bpd"].sum()
        peak_unmet_day = int(df.loc[df["unmet_demand_bpd"].idxmax(), "day"])
        print(f"scenario: {name} (loss {cfg['import_loss_pct']:.0%}, {cfg['duration_days']}d)")
        print(f"  gap covered by SPR:  {covered_spr / total_gap:6.1%}")
        print(f"  gap covered by spot: {covered_spot / total_gap:6.1%}")
        print(f"  unmet demand:        {unmet / total_gap:6.1%}"
              + (f"  (worst on day {peak_unmet_day})" if unmet > 0 else ""))
        print(f"  end inventory:       {df['remaining_inventory_bbl'].iloc[-1] / 1e6:.1f}M bbl "
              f"(floor {STRATEGIC_FLOOR_PCT:.0%} respected)\n")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "spr-drawdown-schedules.csv"
    pd.concat(frames).to_csv(out_path, index=False)
    print(f"wrote schedules -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
