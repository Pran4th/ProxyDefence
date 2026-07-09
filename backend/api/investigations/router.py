from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.api.common.errors import error_response, error_response_invalid
from backend.api.investigations.repository import InvestigationRepository
from backend.api.investigations.schema import CaseCreate, CaseItemAdd, CaseNoteAdd
from backend.api.investigations.service import InvestigationService
from backend.api_service.security import get_current_user

router = APIRouter(prefix="/cases", tags=["Cases & Reports"])


def _build_service(request: Request) -> InvestigationService:
    repo = InvestigationRepository(request.app.state.pg_pool)
    return InvestigationService(repo)


# --- Cases ---

@router.get("/")
async def list_cases(
    request: Request,
    current_user: dict = Depends(get_current_user),
    owner_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    service = _build_service(request)
    owner_filter = owner_id if current_user.get("role") == "admin" else current_user["id"]
    return await service.list_cases(owner_filter, status, limit, offset)


@router.post("/")
async def create_case(
    payload: CaseCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = _build_service(request)
    try:
        return await service.create_case(
            title=payload.title,
            description=payload.description,
            owner_id=current_user["id"],
            priority=payload.priority,
        )
    except ValueError:
        raise error_response_invalid("Invalid case data")


# --- Reports (must be declared before /{case_id} to avoid path collision) ---

@router.get("/reports")
async def list_reports(
    request: Request,
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    service = _build_service(request)
    created_by = None if current_user.get("role") == "admin" else current_user["id"]
    return await service.list_reports(limit, offset, created_by)


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = _build_service(request)
    created_by = None if current_user.get("role") == "admin" else current_user["id"]
    report = await service.get_report(report_id, created_by)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{case_id}")
async def get_case(
    case_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = _build_service(request)
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
    service = _build_service(request)
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
    service = _build_service(request)
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
    service = _build_service(request)
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
    service = _build_service(request)
    case = await service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    service.ensure_access(case, current_user)
    return await service.add_case_note(case_id, payload.note, current_user["id"])


@router.post("/{case_id}/report")
async def generate_case_report(
    case_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = _build_service(request)
    case = await service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    service.ensure_access(case, current_user)
    try:
        return await service.generate_case_report(case_id, current_user["id"])
    except ValueError:
        raise error_response(code="REPORT_ERROR", message="Failed to generate case report", status_code=404)
