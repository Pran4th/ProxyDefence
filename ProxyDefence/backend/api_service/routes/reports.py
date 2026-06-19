from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.api_service.repositories.intelligence import IntelligenceRepository
from backend.api_service.security import get_current_user

router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)


@router.get("/")
async def list_reports(
    request: Request,
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    List all generated intelligence reports.
    """
    repo = IntelligenceRepository(
        request.app.state.pg_pool
    )

    created_by = None if current_user.get("role") == "admin" else current_user["id"]

    return await repo.list_reports(
        limit,
        offset,
        created_by
    )


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific intelligence report.
    """
    repo = IntelligenceRepository(
        request.app.state.pg_pool
    )

    created_by = None if current_user.get("role") == "admin" else current_user["id"]

    report = await repo.get_report(
        report_id,
        created_by
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    return report


@router.post("/case/{case_id}")
async def generate_case_report(
    case_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate an intelligence report from a case.
    """
    repo = IntelligenceRepository(
        request.app.state.pg_pool
    )

    case = await repo.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    if current_user.get("role") != "admin" and case.get("owner_id") != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Case access denied"
        )

    try:
        report = await repo.generate_case_report(
            case_id,
            current_user["id"]
        )

        return report

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )