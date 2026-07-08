from typing import Any

from fastapi import Query

from models import ENTITY_TABLE_NAMES


class FilterParams:
    """Standardized filtering contract for all list endpoints."""

    def __init__(
        self,
        search: str | None = Query(None, description="ILIKE match on name/slug"),
        limit: int = Query(50, ge=1, le=500, description="Max results"),
        offset: int = Query(0, ge=0, description="Result offset"),
        sort: str = Query("name", description="Sort column"),
        order: str = Query("asc", regex="^(asc|desc)$", description="Sort direction"),
        status: str | None = Query(None, description="lifecycle_state filter"),
        operational_status: str | None = Query(None, description="operational_status filter"),
        criticality: str | None = Query(None, description="criticality_level filter"),
        organization: int | None = Query(None, description="organization_id filter"),
        location: str | None = Query(None, description="location_id filter (UUID)"),
        tag: str | None = Query(None, description="tags[] contains filter"),
        is_deleted: bool = Query(False, description="Include soft-deleted?"),
    ):
        self.search = search
        self.limit = limit
        self.offset = offset
        self.sort = sort
        self.order = order
        self.status = status
        self.operational_status = operational_status
        self.criticality = criticality
        self.organization = organization
        self.location = location
        self.tag = tag
        self.is_deleted = is_deleted

    def build_where_clause(self, table: str) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if not self.is_deleted:
            clauses.append("is_deleted = FALSE")

        if self.search:
            clauses.append(f"({table}.name ILIKE ${len(params)+1} OR {table}.slug ILIKE ${len(params)+1})")
            params.append(f"%{self.search}%")

        if self.status:
            clauses.append(f"{table}.status = ${len(params)+1}")
            params.append(self.status)

        if self.operational_status:
            clauses.append(f"{table}.operational_status = ${len(params)+1}")
            params.append(self.operational_status)

        if self.criticality:
            clauses.append(f"{table}.criticality = ${len(params)+1}")
            params.append(self.criticality)

        if self.organization is not None:
            clauses.append(f"{table}.organization_id = ${len(params)+1}")
            params.append(self.organization)

        if self.location:
            clauses.append(f"{table}.location_id = ${len(params)+1}")
            params.append(self.location)

        if self.tag:
            clauses.append(f"${len(params)+1} = ANY({table}.tags)")
            params.append(self.tag)

        where = " AND ".join(clauses) if clauses else "TRUE"
        return where, params

    def build_order_clause(self, table: str) -> str:
        safe_cols = {
            "name", "slug", "created_at", "updated_at",
            "status", "criticality", "importance", "confidence",
            "latitude", "longitude",
        }
        col = self.sort if self.sort in safe_cols else "name"
        return f"{table}.{col} {self.order} NULLS LAST"
