import os

import asyncpg

from backend.shared.database import Pool, bootstrap_schema
from backend.shared.logging_config import get_logger
from backend.shared.paths import infra_sql

logger = get_logger(__name__)

pool = Pool(min_size=2, max_size=10, search_path="energy,public", pool_name="energy-service")

get_pool = pool.get
close_pool = pool.close


async def bootstrap(_pool: asyncpg.Pool | None = None) -> None:
    p = _pool or await pool.get()
    schema_path = str(infra_sql("energy"))
    await bootstrap_schema(
        pool=p,
        schema_name="energy",
        sentinel_table="ports",
        sql_path=schema_path,
        logger=logger,
    )
    intel_path = str(infra_sql("energy_intelligence"))
    await bootstrap_schema(
        pool=p,
        schema_name="energy",
        sentinel_table="risk_factors",
        sql_path=intel_path,
        logger=logger,
    )
    dt_path = str(infra_sql("digital_twin"))
    await bootstrap_schema(
        pool=p,
        schema_name="energy",
        sentinel_table="network_nodes",
        sql_path=dt_path,
        logger=logger,
    )
    proc_path = str(infra_sql("procurement"))
    await bootstrap_schema(
        pool=p,
        schema_name="energy",
        sentinel_table="procurement_runs",
        sql_path=proc_path,
        logger=logger,
    )
    pilot_path = str(infra_sql("pilot_readiness"))
    await bootstrap_schema(
        pool=p,
        schema_name="energy",
        sentinel_table="response_evidence_bundles",
        sql_path=pilot_path,
        logger=logger,
    )
    from seed import load_seed_data
    await load_seed_data(p)
    await _init_procurement(p)

async def _init_procurement(p: asyncpg.Pool) -> None:
    if os.getenv("ENERGY_LOAD_SEED") != "1":
        return
    from services.procurement.supplier_intel import SupplierIntelligence
    from services.procurement.compatibility import RefineryCompatibility
    from services.procurement.optimizer import ProcurementOptimizer
    intel = SupplierIntelligence(p)
    enriched = await intel.enrich_all()
    logger.info("Procurement: enriched %d suppliers", enriched)
    compat = RefineryCompatibility(p)
    compat_result = await compat.compute_all()
    logger.info("Procurement: %s", compat_result)
    opt = ProcurementOptimizer(p)
    route_result = await opt.compute_route_costs()
    logger.info("Procurement: %s", route_result)
    spr_path = str(infra_sql("spr"))
    await bootstrap_schema(
        pool=p,
        schema_name="energy",
        sentinel_table="spr_facilities",
        sql_path=spr_path,
        logger=logger,
    )
    from services.procurement.spr_engine import SPREngine
    spr = SPREngine(p)
    spr_init = await spr.initialize_facilities()
    logger.info("SPR: %s", spr_init)
