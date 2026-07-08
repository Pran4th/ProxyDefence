from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.api.cases.repository import CaseRepository
from backend.api.cases.schema import CaseCreate, CaseItemAdd, CaseNoteAdd
from backend.api.cases.service import CaseService
from backend.api.common.errors import error_response_invalid
from backend.api_service.security import get_current_user

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.get("/")
async def list_cases(
    request: Request,
    current_user: dict = Depends(get_current_user),
    owner_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    repo = CaseRepository(request.app.state.pg_pool)
    service = CaseService(repo)
    owner_filter = owner_id if current_user.get("role") == "admin" else current_user["id"]
    return await service.list_cases(owner_filter, status, limit, offset)


@router.post("/")
async def create_case(
    payload: CaseCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = CaseRepository(request.app.state.pg_pool)
    service = CaseService(repo)
    try:
        return await service.create_case(
            title=payload.title,
            description=payload.description,
            owner_id=current_user["id"],
            priority=payload.priority,
        )
    except ValueError:
        raise error_response_invalid("Invalid case data")


@router.get("/{case_id}")
async def get_case(
    case_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = CaseRepository(request.app.state.pg_pool)
    service = CaseService(repo)
    case = await service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    service.ensure_access(case, current_user)
    return case


@router.post("/{case_id}/items")
async def add_case_item(
    case_id: int,
    payload: CaseItemAdd,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = CaseRepository(request.app.state.pg_pool)
    service = CaseService(repo)
    case = await service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    service.ensure_access(case, current_user)
    try:
        return await service.add_case_item(case_id, payload.item_type, payload.item_id)
    except ValueError:
        raise error_response_invalid("Invalid case item data")


@router.delete("/{case_id}/items/{item_type}/{item_id}")
async def remove_case_item(
    case_id: int,
    item_type: str,
    item_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = CaseRepository(request.app.state.pg_pool)
    service = CaseService(repo)
    case = await service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    service.ensure_access(case, current_user)
    try:
        return await service.remove_case_item(case_id, item_type, item_id)
    except ValueError:
        raise error_response_invalid("Invalid case item data")


@router.get("/{case_id}/notes")
async def list_case_notes(
    case_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    repo = CaseRepository(request.app.state.pg_pool)
    service = CaseService(repo)
    case = await service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    service.ensure_access(case, current_user)
    return await service.list_case_notes(case_id, limit, offset)


@router.post("/{case_id}/notes")
async def add_case_note(
    case_id: int,
    payload: CaseNoteAdd,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = CaseRepository(request.app.state.pg_pool)
    service = CaseService(repo)
    case = await service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    service.ensure_access(case, current_user)
    return await service.add_case_note(case_id, payload.note, current_user["id"])
