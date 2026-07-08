import os

import asyncpg

from backend.shared.database import Pool
from backend.shared.logging_config import get_logger
from backend.shared.paths import infra_sql

from config import POSTGRES_PORT

logger = get_logger(__name__)

pool = Pool(min_size=2, max_size=10, search_path="ml,public", pool_name="ml-platform")

get_pool = pool.get
close_pool = pool.close


async def ensure_schema(_pool: asyncpg.Pool | None = None) -> None:
    p = _pool or await pool.get()
    schema_path = str(infra_sql("ml"))
    if os.path.exists(schema_path):
        async with p.acquire() as conn:
            with open(schema_path) as f:
                sql = f.read()
            await conn.execute(sql)
        logger.info("ml schema applied from %s", schema_path)
    else:
        logger.warning("ml_schema.sql not found at %s, assuming schema exists", schema_path)
