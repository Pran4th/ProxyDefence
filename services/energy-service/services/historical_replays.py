"""Curated, reproducible disruption cases for product evaluation and demos.

The cases are replay inputs, not claims that the simulation predicts the
historical outcome. Their expected effects are directional acceptance checks.
"""

from typing import Any


REPLAY_CASES: dict[str, dict[str, Any]] = {
    "abqaiq-2019": {
        "name": "Abqaiq disruption (2019)",
        "source_window": {"start": "2019-09-14", "end": "2019-09-21", "event": "Abqaiq and Khurais attacks"},
        "signal": {
            "title": "Replay: Saudi supply disruption raises Hormuz exposure",
            "description": "Historical replay of the September 2019 Saudi production disruption. This is replay data, not a live incident.",
            "source": "replay:abqaiq-2019",
            "severity": "high", "risk_dimension": "geopolitical",
            "affected_regions": ["Saudi Arabia", "Strait of Hormuz"],
            "affected_commodities": ["crude oil"], "confidence": 0.8,
            "evidence_urls": ["https://www.iea.org/reports/oil-market-report-september-2019"],
        },
        "expected_effects": {"corridor": "hormuz", "risk_direction": "increase", "scenario": "Strait of Hormuz Partial Closure"},
    },
    "russia-sanctions-2022": {
        "name": "Russian oil sanctions (2022)",
        "source_window": {"start": "2022-12-05", "end": "2022-12-12", "event": "EU price-cap and seaborne oil sanctions"},
        "signal": {
            "title": "Replay: Russian oil sanctions disrupt India-bound crude routes",
            "description": "Historical replay of December 2022 Russia oil sanctions. This is replay data, not a live incident.",
            "source": "replay:russia-sanctions-2022",
            "severity": "high", "risk_dimension": "geopolitical",
            "affected_regions": ["Russia", "India"],
            "affected_commodities": ["crude oil"], "confidence": 0.8,
            "evidence_urls": ["https://www.consilium.europa.eu/en/policies/sanctions-against-russia/sanctions-against-russia-explained/"],
        },
        "expected_effects": {"corridor": "red-sea-suez", "risk_direction": "increase", "scenario": "Russian Export Ban"},
    },
    "red-sea-2024": {
        "name": "Red Sea shipping disruption (2024)",
        "source_window": {"start": "2024-01-01", "end": "2024-01-31", "event": "Houthi attacks and Red Sea diversions"},
        "signal": {
            "title": "Replay: Houthi attacks force Red Sea shipping diversion",
            "description": "Historical replay of January 2024 Red Sea disruption. This is replay data, not a live incident.",
            "source": "replay:red-sea-2024",
            "severity": "high", "risk_dimension": "geopolitical",
            "affected_regions": ["Red Sea", "Yemen", "Suez"],
            "affected_commodities": ["crude oil"], "confidence": 0.85,
            "evidence_urls": ["https://unctad.org/news/red-sea-black-sea-and-panama-canal-disruptions-threaten-global-trade"],
        },
        "expected_effects": {"corridor": "red-sea-suez", "risk_direction": "increase", "scenario": "Red Sea Shipping Disruption"},
    },
}
