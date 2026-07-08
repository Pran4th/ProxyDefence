from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dataset_factory.framework import DatasetFactory
from dataset_factory.config import DatasetFactoryConfig
from dataset_factory.builders import build_preset, PRESET_DATASETS

router = APIRouter(prefix="/api/v1/ml/dataset-factory", tags=["Dataset Factory"])


class FactoryBuildRequest(BaseModel):
    name: str = "energy_infrastructure"
    target_column: str = "criticality_score"
    description: str | None = None
    dataset_type: str = "energy_infrastructure"
    force_synthetic: bool = False
    skip_normalize: bool = False
    skip_clean: bool = False
    skip_validate: bool = False
    skip_quality: bool = False
    skip_eda: bool = False
    skip_features: bool = False
    skip_feature_validation: bool = False
    skip_export: bool = False


class PresetBuildRequest(BaseModel):
    preset: str
    force_synthetic: bool = False
    skip_normalize: bool = False
    skip_clean: bool = False
    skip_validate: bool = False
    skip_quality: bool = False
    skip_eda: bool = False
    skip_features: bool = False
    skip_export: bool = False


@router.post("/build", status_code=201)
async def factory_build(body: FactoryBuildRequest) -> dict[str, Any]:
    config = DatasetFactoryConfig()
    factory = DatasetFactory(config)
    try:
        result = await factory.build(
            name=body.name,
            target_column=body.target_column,
            description=body.description,
            dataset_type=body.dataset_type,
            force_synthetic=body.force_synthetic,
            skip_normalize=body.skip_normalize,
            skip_clean=body.skip_clean,
            skip_validate=body.skip_validate,
            skip_quality=body.skip_quality,
            skip_eda=body.skip_eda,
            skip_features=body.skip_features,
            skip_feature_validation=body.skip_feature_validation,
            skip_export=body.skip_export,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dataset factory build failed: {str(e)}")
    return result.to_dict()


@router.post("/preset", status_code=201)
async def factory_preset(body: PresetBuildRequest) -> dict[str, Any]:
    if body.preset not in PRESET_DATASETS:
        raise HTTPException(status_code=404,
                            detail=f"Preset '{body.preset}' not found. Available: {list(PRESET_DATASETS.keys())}")
    try:
        result = await build_preset(
            body.preset,
            force_synthetic=body.force_synthetic,
            skip_normalize=body.skip_normalize,
            skip_clean=body.skip_clean,
            skip_validate=body.skip_validate,
            skip_quality=body.skip_quality,
            skip_eda=body.skip_eda,
            skip_features=body.skip_features,
            skip_export=body.skip_export,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preset build failed: {str(e)}")
    return result


@router.get("/presets")
async def list_presets() -> dict[str, Any]:
    return {
        "presets": {
            name: {
                "name": cfg["name"],
                "target_column": cfg["target_column"],
                "feature_count": len(cfg.get("feature_configs", [])),
                "description": cfg.get("description", ""),
                "dataset_type": cfg.get("dataset_type", ""),
                "features": [
                    {"name": fc["name"], "transform": fc.get("transform", "identity")}
                    for fc in cfg.get("feature_configs", [])
                ],
            }
            for name, cfg in PRESET_DATASETS.items()
        }
    }
