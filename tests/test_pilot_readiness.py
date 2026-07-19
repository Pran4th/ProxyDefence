"""Fast, deterministic checks for the pilot-readiness decision contract."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENERGY = ROOT / "services" / "energy-service"
sys.path[:0] = [str(ROOT), str(ENERGY)]

from services.evidence import EvidenceService  # noqa: E402
from services.historical_replays import REPLAY_CASES  # noqa: E402


class FakePool:
    def __init__(self, rows=None):
        self.rows = rows or []

    async def fetch(self, query, *args):
        return self.rows


class PilotReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_provenance_defaults_are_truthful(self):
        signal = {
            "source": "replay:abqaiq-2019",
            "created_at": datetime.now(timezone.utc),
            "evidence_urls": [],
        }
        provenance = await EvidenceService(FakePool()).provenance(signal)
        by_key = {item["source"]: item for item in provenance}
        self.assertEqual(by_key["news_signal"]["mode"], "replay")
        self.assertEqual(by_key["ais_chokepoints"]["mode"], "cached")
        self.assertEqual(by_key["sanctions"]["mode"], "disabled")
        self.assertIn("fallback_reason", by_key["commodity_prices"])

    def test_replay_cases_cover_required_events(self):
        self.assertEqual(set(REPLAY_CASES), {"abqaiq-2019", "russia-sanctions-2022", "red-sea-2024"})
        for key, case in REPLAY_CASES.items():
            self.assertTrue(case["signal"]["source"].startswith("replay:"), key)
            self.assertIn("scenario", case["expected_effects"], key)
            self.assertIn("start", case["source_window"], key)

    def test_pilot_schema_has_required_contracts(self):
        sql = (ROOT / "infra" / "sql" / "pilot_readiness_schema.sql").read_text(encoding="utf-8")
        for table in ("intelligence_source_status", "response_evidence_bundles", "decision_approvals", "historical_replay_runs"):
            self.assertIn(table, sql)
        for mode in ("live", "cached", "replay", "fallback"):
            self.assertIn(f"'{mode}'", sql)


if __name__ == "__main__":
    unittest.main()
