from typing import Any

from fastapi import APIRouter, HTTPException, Query

from feature_store.groups import FeatureGroups

router = APIRouter(prefix="/api/v1/ml/features/groups", tags=["ML Feature Groups"])


@router.post("")
async def create_group(name: str, group_type: str,
                        description: str | None = Query(None)) -> dict[str, Any]:
    groups = FeatureGroups()
    try:
        result = await groups.create_group(name, group_type, description)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.get("")
async def list_groups(group_type: str | None = Query(None)) -> list[dict[str, Any]]:
    groups = FeatureGroups()
    return await groups.list_groups(group_type)


@router.get("/{name}")
async def get_group(name: str) -> dict[str, Any]:
    groups = FeatureGroups()
    result = await groups.get_group(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Feature group '{name}' not found")
    return result


@router.post("/{group_name}/features")
async def add_feature_to_group(group_name: str, feature_uuid: str = Query(...),
                                 feature_name: str = Query(...),
                                 feature_version: int = Query(1),
                                 priority: int = Query(0)) -> dict[str, Any]:
    groups = FeatureGroups()
    try:
        result = await groups.add_feature(group_name, feature_uuid, feature_name, feature_version, priority)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.delete("/{group_name}/features/{feature_uuid}")
async def remove_feature_from_group(group_name: str, feature_uuid: str) -> dict:
    groups = FeatureGroups()
    result = await groups.remove_feature(group_name, feature_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="Feature not found in group")
    return {"status": "removed"}


@router.delete("/{name}")
async def deactivate_group(name: str) -> dict:
    groups = FeatureGroups()
    result = await groups.deactivate_group(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found")
    return {"status": "deactivated", "name": name}


@router.get("/health")
async def groups_health():
    return {"status": "healthy", "service": "Feature Groups"}
