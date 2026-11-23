"""Report endpoints: generate overdue reports per ficha."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_snapshot, verify_api_key
from src.api.report_engine import generate_report
from src.api.schemas import (
    OverdueEvidence,
    ReportRequest,
    ReportResponse,
    StudentReportItem,
)

router = APIRouter(prefix="/api", tags=["reports"])


@router.post("/reports/{ficha}", response_model=ReportResponse)
def create_report(
    ficha: str,
    body: ReportRequest,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Generate an overdue report for selected evidences."""
    if not body.evidence_ids:
        raise HTTPException(status_code=400, detail="evidence_ids cannot be empty")

    # Verify ficha exists
    course_exists = any(
        c.get("ficha") == ficha for c in snapshot.get("courses", [])
    )
    if not course_exists:
        raise HTTPException(status_code=404, detail=f"Ficha {ficha} not found")

    result = generate_report(snapshot, ficha, body.evidence_ids)

    students = [
        StudentReportItem(
            user_id=s["user_id"],
            full_name=s["full_name"],
            document=s["document"],
            email=s["email"],
            status=s["status"],
            last_access_days=s["last_access_days"],
            last_access_raw=s["last_access_raw"],
            overdue_evidences=[
                OverdueEvidence(**ev) for ev in s["overdue_evidences"]
            ],
            overdue_count=s["overdue_count"],
        )
        for s in result["students"]
    ]

    return ReportResponse(
        ficha=result["ficha"],
        selected_evidences_count=result["selected_evidences_count"],
        total_students_with_overdue=result["total_students_with_overdue"],
        total_students=result.get("total_students", len(students)),
        students=students,
    )
