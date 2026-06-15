from fastapi import APIRouter, HTTPException, Query, Request

from backend.api_service.repositories.intelligence import IntelligenceRepository

router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)


@router.get("/")
async def list_reports(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    List all generated intelligence reports.
    """
    repo = IntelligenceRepository(
        request.app.state.pg_pool
    )

    return await repo.list_reports(
        limit,
        offset
    )


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    request: Request
):
    """
    Get a specific intelligence report.
    """
    repo = IntelligenceRepository(
        request.app.state.pg_pool
    )

    report = await repo.get_report(
        report_id
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
    created_by: int | None = None
):
    """
    Generate an intelligence report from a case.
    """
    repo = IntelligenceRepository(
        request.app.state.pg_pool
    )

    try:
        report = await repo.generate_case_report(
            case_id,
            created_by
        )

        return report

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )