from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.api_service.repositories.intelligence import IntelligenceRepository

router = APIRouter(
    prefix="/cases",
    tags=["Cases"]
)


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    priority: str = Field(default="medium")


class CaseItemAdd(BaseModel):
    item_type: str = Field(min_length=1, max_length=50)
    item_id: int


class CaseNoteAdd(BaseModel):
    note: str = Field(min_length=3, max_length=5000)


@router.get("/")
async def list_cases(
    request: Request,
    owner_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List all cases with optional owner and status filtering."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    return await repo.list_cases(owner_id, status, limit, offset)


@router.post("/")
async def create_case(
    payload: CaseCreate,
    request: Request,
    owner_id: int | None = None
):
    """Create a new investigation case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    try:
        case = await repo.create_case(
            title=payload.title,
            description=payload.description,
            owner_id=owner_id,
            priority=payload.priority
        )

        return case

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.get("/{case_id}")
async def get_case(
    case_id: int,
    request: Request
):
    """Get a specific case with items and notes."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    case = await repo.get_case(case_id)

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    return case


@router.post("/{case_id}/items")
async def add_case_item(
    case_id: int,
    payload: CaseItemAdd,
    request: Request
):
    """Add an item (alert, event, article, entity) to a case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    try:
        result = await repo.add_case_item(
            case_id,
            payload.item_type,
            payload.item_id
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.delete("/{case_id}/items/{item_type}/{item_id}")
async def remove_case_item(
    case_id: int,
    item_type: str,
    item_id: int,
    request: Request
):
    """Remove an item from a case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    try:
        result = await repo.remove_case_item(
            case_id,
            item_type,
            item_id
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.get("/{case_id}/notes")
async def list_case_notes(
    case_id: int,
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List notes for a specific case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    return await repo.list_case_notes(case_id, limit, offset)


@router.post("/{case_id}/notes")
async def add_case_note(
    case_id: int,
    payload: CaseNoteAdd,
    request: Request,
    created_by: int | None = None
):
    """Add a note to a case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    note = await repo.add_case_note(
        case_id,
        payload.note,
        created_by
    )

    return note
