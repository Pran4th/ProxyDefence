from __future__ import annotations

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class EnergyServiceLoader:
    def __init__(self, energy_service_url: str | None = None):
        self._url = energy_service_url or "http://energy-service:8006"

    def load(self) -> pd.DataFrame:
        try:
            import httpx
            resp = httpx.get(f"{self._url}/api/v1/energy/infrastructure/summary", timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return pd.DataFrame(data)
        except Exception as e:
            logger.warning("EnergyServiceLoader failed, falling back to mock: %s", e)
        return MockDataLoader().load()


class MockDataLoader:
    def __init__(self, random_seed: int = 42, n_samples: int = 500):
        self._random_seed = random_seed
        self._n_samples = n_samples

    def load(self) -> pd.DataFrame:
        rs = np.random.RandomState(self._random_seed)
        n = self._n_samples
        regions = ["North America", "Europe", "Asia Pacific", "Middle East", "Africa", "South America"]
        return pd.DataFrame({
            "criticality_score": rs.randint(0, 4, n),
            "region": rs.choice(regions, n),
            "throughput_mtpa": rs.exponential(50, n),
            "capacity_mw": rs.exponential(200, n),
            "age_years": rs.randint(1, 60, n),
            "num_employees": rs.randint(50, 5000, n),
            "is_operational": rs.choice([0, 1], n),
            "investment_million": rs.exponential(100, n),
            "safety_incidents": rs.poisson(2, n),
            "distance_to_port_km": rs.exponential(300, n),
        })
