from typing import Any

from fastapi import APIRouter, HTTPException, Query

from feature_store.transforms import TRANSFORM_REGISTRY
from feature_store.transforms_registry import TransformRegistry

router = APIRouter(prefix="/api/v1/ml/features/transforms", tags=["ML Feature Transforms"])


@router.get("")
async def list_transforms(transform_type: str | None = Query(None)) -> list[dict[str, Any]]:
    registry = TransformRegistry()
    return await registry.list_transforms(transform_type)


@router.get("/{name}")
async def get_transform(name: str) -> dict[str, Any]:
    registry = TransformRegistry()
    result = await registry.get_transform(name)
    if not result:
        detail = f"Transform '{name}' not found. Available: {sorted(TRANSFORM_REGISTRY.keys())}"
        raise HTTPException(status_code=404, detail=detail)
    return result


@router.get("/builtins/list")
async def list_builtin_transforms() -> dict[str, Any]:
    return {
        "transforms": sorted(TRANSFORM_REGISTRY.keys()),
        "count": len(TRANSFORM_REGISTRY),
    }


@router.get("/{name}/schema")
async def get_transform_schema(name: str) -> dict[str, Any]:
    if name not in TRANSFORM_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown transform: {name}")
    cls = TRANSFORM_REGISTRY[name]
    import inspect
    sig = inspect.signature(cls.__init__)
    params = {}
    for pname, p in sig.parameters.items():
        if pname == "self":
            continue
        default = None if p.default is inspect.Parameter.empty else p.default
        params[pname] = {
            "type": str(p.annotation) if p.annotation is not inspect.Parameter.empty else "Any",
            "default": default,
            "required": p.default is inspect.Parameter.empty,
        }
    return {
        "name": name,
        "class": cls.__name__,
        "doc": (cls.__doc__ or "").strip(),
        "parameters": params,
    }


@router.post("/register-builtins")
async def register_builtins() -> dict:
    registry = TransformRegistry()
    await registry.register_builtins()
    return {"status": "registered", "count": len(TRANSFORM_REGISTRY)}


@router.get("/health")
async def transforms_health():
    return {"status": "healthy", "service": "Feature Transforms"}
