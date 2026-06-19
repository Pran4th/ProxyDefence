from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.api_service.repositories.intelligence import IntelligenceRepository
from backend.api_service.security import get_current_user

router = APIRouter(
    prefix="/cases",
    tags=["Cases"]
)


def _ensure_case_access(case: dict, current_user: dict) -> None:
    if current_user.get("role") == "admin":
        return
    if case.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Case access denied")


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
    current_user: dict = Depends(get_current_user),
    owner_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List all cases with optional owner and status filtering."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    owner_filter = owner_id if current_user.get("role") == "admin" else current_user["id"]
    return await repo.list_cases(owner_filter, status, limit, offset)


@router.post("/")
async def create_case(
    payload: CaseCreate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Create a new investigation case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    try:
        case = await repo.create_case(
            title=payload.title,
            description=payload.description,
            owner_id=current_user["id"],
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
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific case with items and notes."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    case = await repo.get_case(case_id)

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    _ensure_case_access(case, current_user)

    return case


@router.post("/{case_id}/items")
async def add_case_item(
    case_id: int,
    payload: CaseItemAdd,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Add an item (alert, event, article, entity) to a case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    case = await repo.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    _ensure_case_access(case, current_user)

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
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Remove an item from a case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    case = await repo.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    _ensure_case_access(case, current_user)

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
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List notes for a specific case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    case = await repo.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    _ensure_case_access(case, current_user)

    return await repo.list_case_notes(case_id, limit, offset)


@router.post("/{case_id}/notes")
async def add_case_note(
    case_id: int,
    payload: CaseNoteAdd,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Add a note to a case."""
    repo = IntelligenceRepository(request.app.state.pg_pool)

    case = await repo.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    _ensure_case_access(case, current_user)

    note = await repo.add_case_note(
        case_id,
        payload.note,
        current_user["id"]
    )

    return note
