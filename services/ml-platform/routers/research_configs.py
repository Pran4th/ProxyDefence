from typing import Any

from fastapi import APIRouter, HTTPException, Query

from research.config import ResearchConfigLoader
from research.utils.config_loader import ConfigLoader

router = APIRouter(prefix="/api/v1/ml/research/configs", tags=["ML Research Configs"])


@router.get("")
async def list_configs(config_type: str | None = Query(None)) -> list[dict[str, Any]]:
    loader = ResearchConfigLoader()
    return loader.list_configs(config_type)


@router.get("/schema/default")
async def get_default_config(name: str = "experiment",
                               experiment_type: str = "classification") -> dict:
    cfg = ResearchConfigLoader.build_default_config(name, experiment_type)
    return cfg


@router.post("/validate")
async def validate_config(path: str = Query(...)) -> dict:
    loader = ResearchConfigLoader()
    try:
        config = loader.load(path)
        return {"valid": True, "experiment": config.get("experiment", {}).get("name")}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@router.get("/health")
async def configs_health():
    return {"status": "healthy", "service": "Research Configs"}
