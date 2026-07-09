from __future__ import annotations

import numpy as np
import pandas as pd
import requests

from backend.shared.logging_config import get_logger
from config import ENERGY_SERVICE_URL

logger = get_logger(__name__)

ENERGY_TABLES = [
    "ports", "oil_fields", "gas_fields", "pipelines", "refineries",
    "power_plants", "storage_facilities",
]

CRITICALITY_MAP = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class EnergyServiceLoader:
    def __init__(self, base_url: str = ENERGY_SERVICE_URL):
        self._base_url = base_url

    def _fetch_table(self, table: str) -> pd.DataFrame:
        url = f"{self._base_url}/api/v1/energy/{table}?limit=10000"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return pd.DataFrame(items) if items else pd.DataFrame()
        except requests.RequestException as e:
            logger.warning("EnergyServiceLoader: failed to fetch %s: %s", table, e)
            return pd.DataFrame()

    def load(self) -> pd.DataFrame:
        frames = []
        for table in ENERGY_TABLES:
            df = self._fetch_table(table)
            if not df.empty:
                df["entity_type"] = table
                frames.append(df)

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True, sort=False)
        if "criticality" in combined.columns:
            combined["criticality_score"] = combined["criticality"].map(CRITICALITY_MAP).fillna(1).astype(int)
        return combined


class MockDataLoader:
    REGIONS = ["Middle East", "North America", "Europe", "Asia Pacific", "Africa", "South America"]
    CRITICALITY = ["low", "medium", "high", "critical"]

    def __init__(self, random_seed: int = 42, n_samples: int = 500):
        self._random_seed = random_seed
        self._n_samples = n_samples

    def load(self) -> pd.DataFrame:
        rs = np.random.RandomState(self._random_seed)
        n = self._n_samples

        criticality_idx = rs.randint(0, 4, n)
        df = pd.DataFrame({
            "entity_id": [f"mock-{i:05d}" for i in range(n)],
            "entity_type": rs.choice(["pipeline", "refinery", "port", "oil_field", "power_plant"], n),
            "region": rs.choice(self.REGIONS, n),
            "criticality": [self.CRITICALITY[i] for i in criticality_idx],
            "criticality_score": criticality_idx,
            "throughput_mtpa": np.round(rs.uniform(0.5, 120.0, n), 2),
            "latitude": rs.uniform(-60, 70, n),
            "longitude": rs.uniform(-180, 180, n),
            "operational_status": rs.choice(["active", "maintenance", "offline"], n, p=[0.85, 0.1, 0.05]),
        })
        return df
