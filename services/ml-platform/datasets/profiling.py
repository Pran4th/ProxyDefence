from __future__ import annotations

import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class DatasetProfiler:
    @staticmethod
    async def profile(
        df: pd.DataFrame, dataset_name: str, version: int,
    ) -> dict:
        profile = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
        }
        logger.info(
            "profiling complete",
            dataset=dataset_name,
            version=version,
            columns=profile["column_count"],
        )
        return profile
