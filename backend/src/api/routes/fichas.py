"""Ficha-specific endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.alerts import generate_alerts
from src.api.course_stats import build_active_ids, compute_active_stats, resolve_stats
from src.api.dependencies import get_snapshot, verify_api_key
from src.api.schemas import (
    AlertsResponse,
    EvidenceItem,
    FichaDetailResponse,
    FichaSummaryItem,
    GradeItem,
    PendingEvidence,
    PendingStudent,
    PendingSubmissionsResponse,
    StudentItem,
)
from src.models.schemas import GradeStatus

router = APIRouter(prefix="/api", tags=["fichas"])


def _find_course_by_ficha(snapshot: dict, ficha: str) -> tuple[dict, dict]:
    """Find course and summary by ficha number. Raises 404 if not found."""
    courses = snapshot.get("courses", [])
    summaries = snapshot.get("summaries", [])

    course = None
    for c in courses:
        if c["ficha"] == ficha:
            course = c
            break

    if course is None:
        raise HTTPException(status_code=404, detail=f"Ficha {ficha} not found")

    summary = {}
    for s in summaries:
        if s["course_id"] == course["course_id"]:
            summary = s
            break

    return course, summary


@router.get("/fichas", response_model=list[FichaSummaryItem])
def list_fichas(
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """List all fichas with their summaries (pending/completion over active students)."""
    courses = snapshot.get("courses", [])
    summaries = snapshot.get("summaries", [])

    name_map = {c["course_id"]: c["course_name"] for c in courses}
    active_ids_by_course = build_active_ids(snapshot.get("participants", []))
    grade_data_by_course = {c["course_id"]: c for c in courses}
    result: list[FichaSummaryItem] = []

    for s in summaries:
        course_id = s["course_id"]
        stats = resolve_stats(
            grade_data_by_course.get(course_id),
            active_ids_by_course.get(course_id),
            s,
        )
        result.append(FichaSummaryItem(
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

    return result


@router.get("/fichas/{ficha}", response_model=FichaDetailResponse)
def ficha_detail(
    ficha: str,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Detailed view for a single ficha."""
    course, summary = _find_course_by_ficha(snapshot, ficha)

    # Build participant status map from participants data
    participant_status: dict[int, str] = {}
    for cp in snapshot.get("participants", []):
        if cp.get("ficha") == ficha:
            for p in cp.get("participants", []):
                participant_status[p["user_id"]] = p.get("status", "Activo")
            break

    active_ids = {
        uid for uid, status in participant_status.items() if status == "Activo"
    }
    # Si no hay datos de participantes, no filtramos (todos cuentan)
    has_status = bool(participant_status)

    def is_active(user_id: int) -> bool:
        return not has_status or user_id in active_ids

    # Evidence stats — solo aprendices activos
    evidences: list[EvidenceItem] = []
    for ev in course.get("evidences", []):
        item_id = ev["item_id"]
        approved = 0
        disapproved = 0
        pending = 0
        for student in course.get("students", []):
            if not is_active(student["user_id"]):
                continue
            grade = student.get("grades", {}).get(str(item_id))
            if grade is None:
                continue
            v = grade["value"]
            if v == GradeStatus.APPROVED.value:
                approved += 1
            elif v == GradeStatus.DISAPPROVED.value:
                disapproved += 1
            elif v == GradeStatus.PENDING.value:
                pending += 1

        evidences.append(EvidenceItem(
            item_id=item_id,
            name=ev["name"],
            category=ev["category"],
            total_approved=approved,
            total_disapproved=disapproved,
            total_pending=pending,
        ))

    # Build student items
    students: list[StudentItem] = []
    for st in course.get("students", []):
        approved = 0
        disapproved = 0
        pending = 0
        grades_out: dict[int, GradeItem] = {}

        for eid_str, grade in st.get("grades", {}).items():
            eid = int(eid_str)
            v = grade["value"]
            if v == GradeStatus.APPROVED.value:
                approved += 1
            elif v == GradeStatus.DISAPPROVED.value:
                disapproved += 1
            elif v == GradeStatus.PENDING.value:
                pending += 1

            grades_out[eid] = GradeItem(
                evidence_id=eid,
                value=v,
                passed=grade["passed"],
            )

        students.append(StudentItem(
            user_id=st["user_id"],
            full_name=st["full_name"],
            document=st["document"],
            email=st["email"],
            approved=approved,
            disapproved=disapproved,
            pending=pending,
            grades=grades_out,
            status=participant_status.get(st["user_id"], "Activo"),
        ))

    # Avance solo de aprendices activos (los suspendidos no cuentan)
    if active_ids:
        active_stats = compute_active_stats(course, active_ids)
        total_active = active_stats["active_students"]
        completion = active_stats["completion_percentage"]
    else:
        # Sin datos de participantes: fallback al summary crudo
        total_active = summary.get("total_students", len(students))
        completion = summary.get("completion_percentage", 0.0)

    return FichaDetailResponse(
        ficha=course["ficha"],
        course_id=course["course_id"],
        course_name=course["course_name"],
        total_students=summary.get("total_students", len(students)),
        total_active=total_active,
        total_evidences=summary.get("total_evidences", len(evidences)),
        completion_percentage=completion,
        students=students,
        evidences=evidences,
    )


@router.get("/fichas/{ficha}/pendientes", response_model=PendingSubmissionsResponse)
def ficha_pendientes(
    ficha: str,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Pending items for a ficha, sorted by urgency (active learners only)."""
    course, summary = _find_course_by_ficha(snapshot, ficha)

    # Estado de matrícula: los suspendidos no entran al trabajo pendiente
    participant_status: dict[int, str] = {}
    for cp in snapshot.get("participants", []):
        if cp.get("ficha") == ficha:
            for p in cp.get("participants", []):
                participant_status[p["user_id"]] = p.get("status", "Activo")
            break
    has_status = bool(participant_status)

    def is_active(user_id: int) -> bool:
        return not has_status or participant_status.get(user_id) == "Activo"

    active_students = [s for s in course.get("students", []) if is_active(s["user_id"])]
    total_active = len(active_students)
    evidence_map = {ev["item_id"]: ev for ev in course.get("evidences", [])}

    # Pending by student (solo activos)
    by_student: list[PendingStudent] = []
    pending_by_ev: dict[int, int] = {}
    for st in active_students:
        pending_eids: list[int] = []
        for eid_str, grade in st.get("grades", {}).items():
            if grade["value"] == GradeStatus.PENDING.value:
                eid = int(eid_str)
                pending_eids.append(eid)
                pending_by_ev[eid] = pending_by_ev.get(eid, 0) + 1

        if pending_eids:
            by_student.append(PendingStudent(
                user_id=st["user_id"],
                full_name=st["full_name"],
                document=st["document"],
                pending_count=len(pending_eids),
                pending_evidences=pending_eids,
            ))

    by_student.sort(key=lambda s: -s.pending_count)

    # Pending by evidence (recomputado sobre activos), % sobre activos
    by_evidence: list[PendingEvidence] = []
    for eid, count in pending_by_ev.items():
        ev = evidence_map.get(eid, {})
        pct = round((count / total_active) * 100, 1) if total_active > 0 else 0.0
        by_evidence.append(PendingEvidence(
            item_id=eid,
            name=ev.get("name", f"Evidence {eid}"),
            category=ev.get("category", ""),
            pending_count=count,
            pending_percentage=pct,
        ))

    by_evidence.sort(key=lambda e: -e.pending_count)

    return PendingSubmissionsResponse(
        ficha=ficha,
        by_evidence=by_evidence,
        by_student=by_student,
    )


@router.get("/alerts", response_model=AlertsResponse)
def alerts(
    ficha: str | None = None,
    severity: str | None = None,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Generated alerts, optionally filtered by ficha and/or severity."""
    all_alerts = generate_alerts(snapshot)

    filtered = all_alerts
    if ficha:
        filtered = [a for a in filtered if a.ficha == ficha]
    if severity:
        filtered = [a for a in filtered if a.severity == severity]

    return AlertsResponse(alerts=filtered, total=len(filtered))
