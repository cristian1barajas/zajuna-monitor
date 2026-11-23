"""Dashboard and general endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.alerts import generate_alerts
from src.api.course_stats import build_active_ids, resolve_stats
from src.api.dependencies import get_snapshot, verify_api_key
from src.api.schemas import (
    DashboardResponse,
    FichaSummaryItem,
    HealthResponse,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request):
    """Health check; con token válido incluye la última sincronización del instructor."""
    if getattr(request.state, "user", None) is None:
        # Sin identificar no se revela nada del snapshot.
        return HealthResponse(status="ok", last_scrape=None, courses_count=0, errors_count=0)
    try:
        snapshot = get_snapshot(request)
    except HTTPException:
        return HealthResponse(status="ok", last_scrape=None, courses_count=0, errors_count=0)
    ts_str = snapshot.get("timestamp")
    last_scrape = datetime.fromisoformat(ts_str) if ts_str else None

    return HealthResponse(
        status="ok",
        last_scrape=last_scrape,
        courses_count=len(snapshot.get("courses", [])),
        errors_count=len(snapshot.get("errors", [])),
    )


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Global summary across all fichas (active students only)."""
    summaries = snapshot.get("summaries", [])
    courses = snapshot.get("courses", [])
    participants_list = snapshot.get("participants", [])

    # Build course name lookup
    name_map = {c["course_id"]: c["course_name"] for c in courses}

    # Active user_ids and grade data per course_id
    active_ids_by_course = build_active_ids(participants_list)
    grade_data_by_course = {c["course_id"]: c for c in courses}

    fichas: list[FichaSummaryItem] = []
    total_students = 0
    total_active = 0
    total_evidences = 0
    total_pending = 0
    total_cells_all = 0
    weighted_completion_sum = 0.0

    for s in summaries:
        course_id = s["course_id"]
        stats = resolve_stats(
            grade_data_by_course.get(course_id),
            active_ids_by_course.get(course_id),
            s,
        )

        fichas.append(FichaSummaryItem(
            ficha=s["ficha"],
            course_name=name_map.get(course_id, ""),
            course_id=course_id,
            total_students=s["total_students"],
            total_active=stats["active_students"],
            total_evidences=s["total_evidences"],
            total_pending=stats["pending"],
            total_graded=stats["approved"] + stats["disapproved"],
            completion_percentage=stats["completion_percentage"],
        ))
        total_students += s["total_students"]
        total_active += stats["active_students"]
        total_evidences += s["total_evidences"]
        total_pending += stats["pending"]
        weighted_completion_sum += stats["completion_percentage"] * stats["cells"]
        total_cells_all += stats["cells"]

    overall_completion = (
        round(weighted_completion_sum / total_cells_all, 1)
        if total_cells_all > 0 else 0.0
    )

    ts_str = snapshot.get("timestamp")
    last_scrape = datetime.fromisoformat(ts_str) if ts_str else None

    alerts = generate_alerts(snapshot)

    return DashboardResponse(
        fichas=fichas,
        total_students=total_students,
        total_active=total_active,
        total_evidences=total_evidences,
        total_pending=total_pending,
        overall_completion=overall_completion,
        last_scrape=last_scrape,
        alerts_count=len(alerts),
    )


@router.get("/snapshot/latest")
def snapshot_latest(
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Return the full raw snapshot JSON."""
    return snapshot
