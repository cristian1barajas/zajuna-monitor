"""API endpoints for due process tracking and email generation."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from src.api.dependencies import get_snapshot, verify_api_key
from src.api.email_templates import generate_email
from src.api.eml_export import EmlDraft, build_eml, build_eml_zip, eml_filename, zip_filename
from src.api.schemas import (
    AdvanceRequest,
    AdvanceResponse,
    DueProcessHistoryEntry,
    DueProcessRecord,
    DueProcessResponse,
    DueProcessStudentResponse,
    EmailDraft,
    EmailDraftRequest,
    EmailDraftsResponse,
    EmlExportRequest,
)
from src.models.schemas import GradeStatus
from src.store.cached_json import read_json_cached
from src.store.due_process_store import (
    STAGE_LABELS,
    advance_due_process,
    delete_due_process,
    get_next_stage,
    load_due_process,
)
from src.store.novedades_store import load_novedades_set

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["due-process"])


def _record_to_schema(raw: dict) -> DueProcessRecord:
    """Convert a raw dict record to a DueProcessRecord schema."""
    return DueProcessRecord(
        user_id=raw["user_id"],
        full_name=raw["full_name"],
        document=raw["document"],
        current_stage=raw["current_stage"],
        current_stage_label=STAGE_LABELS.get(raw["current_stage"], raw["current_stage"]),
        history=[
            DueProcessHistoryEntry(
                stage=h["stage"],
                stage_label=STAGE_LABELS.get(h["stage"], h["stage"]),
                date=h["date"],
                evidence_ids=h.get("evidence_ids", []),
                evidence_names=h.get("evidence_names", []),
                email_generated=h.get("email_generated", False),
            )
            for h in raw.get("history", [])
        ],
    )


@router.get("/due-process/{ficha}", response_model=DueProcessResponse)
def get_due_process(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Get all due process records for a ficha."""
    data = load_due_process(ficha)
    if data is None:
        return DueProcessResponse(
            ficha=ficha,
            records=[],
            total_records=0,
        )

    records = [
        _record_to_schema(rec)
        for rec in data.get("records", {}).values()
    ]

    return DueProcessResponse(
        ficha=ficha,
        updated_at=data.get("updated_at"),
        records=records,
        total_records=len(records),
    )


@router.get("/due-process/{ficha}/{user_id}", response_model=DueProcessStudentResponse)
def get_student_due_process(
    ficha: str,
    user_id: int,
    _key: str = Depends(verify_api_key),
):
    """Get due process history for a specific student."""
    data = load_due_process(ficha)
    if data is None:
        raise HTTPException(status_code=404, detail="No due process records for this ficha")

    record = data.get("records", {}).get(str(user_id))
    if record is None:
        raise HTTPException(status_code=404, detail=f"No due process record for user {user_id}")

    return DueProcessStudentResponse(
        ficha=ficha,
        record=_record_to_schema(record),
    )


@router.post("/due-process/{ficha}/email-drafts", response_model=EmailDraftsResponse)
def generate_email_drafts(
    ficha: str,
    body: EmailDraftRequest,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Generate email previews for selected students. Does NOT persist."""
    if not body.user_ids:
        raise HTTPException(status_code=400, detail="user_ids cannot be empty")

    # Build student lookup from snapshot
    student_map, participant_map, evidence_info = _build_lookups(snapshot, ficha)

    # Load existing due process to know current stages
    dp_data = load_due_process(ficha)
    dp_records = dp_data.get("records", {}) if dp_data else {}

    # Load submission status cache (yellow cells = submitted but ungraded)
    submitted_cells = _load_submission_status(ficha)

    # Load novedades to exclude students with pending administrative processes
    novedad_ids = load_novedades_set(ficha)

    drafts = []
    for uid in body.user_ids:
        # Skip students with novedades (e.g. cancellation in progress)
        if uid in novedad_ids:
            logger.info("User %d has novedad, skipping email draft", uid)
            continue

        # Skip officially suspended students (already cancelled in Zajuna)
        participant = participant_map.get(uid, {})
        if participant.get("status") == "Suspendido":
            logger.info("User %d is suspended, skipping email draft", uid)
            continue

        student = student_map.get(uid)
        if student is None:
            logger.warning("User %d not found in snapshot for ficha %s", uid, ficha)
            continue

        # Filter evidences: only those this student hasn't delivered or failed
        ev_names = _filter_evidences_for_student(
            student, body.evidence_ids, evidence_info, submitted_cells,
        )

        if not ev_names:
            # Student has no actionable pending evidences — skip
            logger.info(
                "User %d (%s) has no pending evidences after filtering, skipping",
                uid, student["full_name"],
            )
            continue
        current_record = dp_records.get(str(uid))
        current_stage = current_record["current_stage"] if current_record else None
        next_stage = get_next_stage(current_stage)

        last_access = participant.get("last_access_raw", "No disponible")
        history = current_record.get("history", []) if current_record else []

        email = generate_email(
            stage=next_stage,
            student_name=student["full_name"],
            student_document=student["document"],
            ficha=ficha,
            evidence_names=ev_names,
            last_access_info=last_access,
            history=history,
        )

        drafts.append(EmailDraft(
            user_id=uid,
            full_name=student["full_name"],
            document=student["document"],
            email=student["email"],
            stage=email["stage"],
            stage_label=email["stage_label"],
            subject=email["subject"],
            body=email["body"],
        ))

    return EmailDraftsResponse(
        ficha=ficha,
        drafts=drafts,
        total=len(drafts),
    )


@router.post("/due-process/{ficha}/email-drafts/eml")
def export_email_drafts_eml(
    ficha: str,
    body: EmlExportRequest,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Descarga los borradores como .eml para abrir en Outlook. Does NOT persist.

    Un borrador devuelve el .eml directo; varios (o ``as_zip``), un .zip con
    un .eml cada uno.
    Solo se aceptan aprendices de una ficha visible para el instructor.
    """
    student_map, _, _ = _build_lookups(snapshot, ficha)
    if not student_map:
        raise HTTPException(status_code=404, detail=f"Ficha {ficha} not found")

    unknown = sorted({d.user_id for d in body.drafts} - student_map.keys())
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Users not in ficha {ficha}: {unknown}",
        )

    drafts = [
        EmlDraft(
            full_name=d.full_name,
            email=d.email,
            subject=d.subject,
            body=d.body,
            stage=d.stage,
        )
        for d in body.drafts
    ]

    if len(drafts) == 1 and not body.as_zip:
        content = build_eml(drafts[0])
        filename = eml_filename(1, drafts[0])
        media_type = "message/rfc822"
    else:
        content, _ = build_eml_zip(drafts)
        filename = zip_filename(ficha)
        media_type = "application/zip"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/due-process/{ficha}/advance", response_model=AdvanceResponse)
def advance_students(
    ficha: str,
    body: AdvanceRequest,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Advance selected students to the next due process stage. Persists."""
    if not body.user_ids:
        raise HTTPException(status_code=400, detail="user_ids cannot be empty")

    student_map, participant_map, evidence_info = _build_lookups(snapshot, ficha)

    # Load submission status cache (yellow cells)
    submitted_cells = _load_submission_status(ficha)

    # Load novedades to exclude students with pending administrative processes
    novedad_ids = load_novedades_set(ficha)

    records = []
    for uid in body.user_ids:
        # Skip students with novedades (e.g. cancellation in progress)
        if uid in novedad_ids:
            logger.info("User %d has novedad, skipping advance", uid)
            continue

        # Skip officially suspended students (already cancelled in Zajuna)
        participant = participant_map.get(uid, {})
        if participant.get("status") == "Suspendido":
            logger.info("User %d is suspended, skipping advance", uid)
            continue

        student = student_map.get(uid)
        if student is None:
            logger.warning("User %d not found in snapshot for ficha %s", uid, ficha)
            continue

        # Filter evidences per student
        ev_names = _filter_evidences_for_student(
            student, body.evidence_ids, evidence_info, submitted_cells,
        )

        if not ev_names:
            logger.info(
                "User %d (%s) has no pending evidences after filtering, skipping advance",
                uid, student["full_name"],
            )
            continue

        raw = advance_due_process(
            ficha=ficha,
            user_id=uid,
            full_name=student["full_name"],
            document=student["document"],
            evidence_ids=body.evidence_ids,
            evidence_names=ev_names,
        )
        records.append(_record_to_schema(raw))

    return AdvanceResponse(
        ficha=ficha,
        advanced=len(records),
        records=records,
    )


@router.delete("/due-process/{ficha}")
def reset_due_process(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Delete all due process records for a ficha."""
    deleted = delete_due_process(ficha)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No due process records for ficha {ficha}")
    return {"deleted": True}


def _build_lookups(
    snapshot: dict, ficha: str
) -> tuple[dict[int, dict], dict[int, dict], dict[int, dict]]:
    """Build student, participant, and evidence lookup maps from snapshot."""
    student_map: dict[int, dict] = {}
    evidence_info: dict[int, dict] = {}

    for course in snapshot.get("courses", []):
        if course.get("ficha") == ficha:
            for student in course.get("students", []):
                student_map[student["user_id"]] = student
            for ev in course.get("evidences", []):
                evidence_info[ev["item_id"]] = {
                    "name": ev["name"],
                    "category": ev["category"],
                }
            break

    participant_map: dict[int, dict] = {}
    for cp in snapshot.get("participants", []):
        if cp.get("ficha") == ficha:
            for p in cp.get("participants", []):
                participant_map[p["user_id"]] = p
            break

    return student_map, participant_map, evidence_info


def _load_submission_status(ficha: str) -> set[str]:
    """Load the submission status cache and return the set of pending_cells.

    Each entry is "item_id:user_id" for cells that have been submitted
    but not yet graded (yellow cells).

    Cached by mtime (read_json_cached). The writer lives in
    routes/pending_grading.py and does not call invalidate(); the new
    mtime after each refresh invalidates the entry naturally.
    """
    from src.config import SUBMISSION_STATUS_DIR
    from src.store.instructor_scope import scoped_dir
    path = scoped_dir(SUBMISSION_STATUS_DIR) / f"{ficha}.json"
    try:
        data = read_json_cached(path, default=None)
        if data is None:
            return set()
        return set(data.get("pending_cells", []))
    except Exception:
        return set()


def _filter_evidences_for_student(
    student: dict,
    evidence_ids: list[int],
    evidence_info: dict[int, dict],
    submitted_cells: set[str],
) -> list[str]:
    """Filter evidence names to only those the student actually needs to address.

    Excludes:
    - Approved (A): student already passed
    - Submitted but ungraded (yellow): student delivered, instructor hasn't graded yet

    Includes:
    - Pending (-): not submitted
    - Disapproved (D): needs to redo
    """
    user_id = student["user_id"]
    grades = student.get("grades", {})
    names: list[str] = []

    for eid in evidence_ids:
        grade = grades.get(str(eid))
        if grade is None:
            # No grade data — include as pending
            info = evidence_info.get(eid, {})
            names.append(info.get("name", f"Evidencia {eid}"))
            continue

        value = grade.get("value")

        if value == GradeStatus.APPROVED.value:
            # Already approved — skip
            continue

        if value == GradeStatus.PENDING.value:
            # Check if it's a yellow cell (submitted but ungraded)
            cell_key = f"{eid}:{user_id}"
            if cell_key in submitted_cells:
                # Student submitted — skip (not their fault)
                continue

        # Pending (not submitted) or Disapproved — include
        info = evidence_info.get(eid, {})
        names.append(info.get("name", f"Evidencia {eid}"))

    return names
