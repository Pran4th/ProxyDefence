from typing import Any

from backend.shared.logging_config import get_logger
from db import get_pool
from feature_store.transforms import TRANSFORM_REGISTRY

logger = get_logger(__name__)


class TransformRegistry:
    @staticmethod
    async def register_builtins():
        pool = await get_pool()
        for name, transform_cls in TRANSFORM_REGISTRY.items():
            doc = (transform_cls.__doc__ or "").strip()
            import inspect
            sig = inspect.signature(transform_cls.__init__)
            params = {}
            for pname, p in sig.parameters.items():
                if pname == "self":
                    continue
                default = None if p.default is inspect.Parameter.empty else str(p.default)
                params[pname] = {
                    "type": str(p.annotation) if p.annotation is not inspect.Parameter.empty else "Any",
                    "default": default,
                }
            await pool.execute(
                "INSERT INTO ml.transform_registry (name, transform_type, description, parameters_schema, is_builtin) "
                "VALUES ($1, $2, $3, $4, TRUE) "
                "ON CONFLICT (name) DO NOTHING",
                name, transform_cls.__name__, doc, params,
            )
        logger.info("registered %d built-in transforms", len(TRANSFORM_REGISTRY))

    @staticmethod
    async def list_transforms(transform_type: str | None = None,
                               active_only: bool = True) -> list[dict[str, Any]]:
        pool = await get_pool()
        conditions = ["1=1"]
        params: list[Any] = []
        if transform_type:
            conditions.append(f"transform_type = ${len(params) + 1}")
            params.append(transform_type)
        if active_only:
            conditions.append("is_active = TRUE")
        where = " AND ".join(conditions)
        rows = await pool.fetch(
            f"SELECT * FROM ml.transform_registry WHERE {where} ORDER BY name",
            *params,
        )
        return [dict(r) for r in rows]

    @staticmethod
    async def get_transform(name: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.transform_registry WHERE name = $1", name,
        )
        return dict(row) if row else None

    @staticmethod
    def instantiate(name: str, **kwargs) -> Any:
        if name not in TRANSFORM_REGISTRY:
            raise ValueError(f"Unknown transform: {name}. Available: {sorted(TRANSFORM_REGISTRY.keys())}")
        return TRANSFORM_REGISTRY[name](**kwargs)
