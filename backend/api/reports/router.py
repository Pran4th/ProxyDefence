from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.api.common.errors import error_response
from backend.api.reports.repository import ReportRepository
from backend.api.reports.service import ReportService
from backend.api_service.security import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/")
async def list_reports(
    request: Request,
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    repo = ReportRepository(request.app.state.pg_pool)
    service = ReportService(repo)
    created_by = None if current_user.get("role") == "admin" else current_user["id"]
    return await service.list_reports(limit, offset, created_by)


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = ReportRepository(request.app.state.pg_pool)
    service = ReportService(repo)
    created_by = None if current_user.get("role") == "admin" else current_user["id"]
    report = await service.get_report(report_id, created_by)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/case/{case_id}")
async def generate_case_report(
    case_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = ReportRepository(request.app.state.pg_pool)
    service = ReportService(repo)
    try:
        report = await service.generate_case_report(case_id, current_user["id"])
        return report
    except ValueError:
        raise error_response(code="REPORT_ERROR", message="Failed to generate case report", status_code=404)
