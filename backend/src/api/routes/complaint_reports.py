"""Complaint reports (Informes de Queja) endpoints."""
from __future__ import annotations

import io
import logging
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.dependencies import get_snapshot, verify_api_key
from src.api.docx_generator import generate_complaint_docx
from src.api.schemas import EvidenceItem
from src.api.security import get_security_settings
from src.models.schemas import GradeStatus
from src.store.due_process_store import load_due_process
from src.store.instructor_scope import current_instructor
from src.store.phone_data_store import load_phone_data
from src.store.rap_mapping_store import load_rap_mapping

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["complaint-reports"])

# Temporary storage for participant screenshot images (per ficha)
_screenshot_store: dict[tuple[str | None, str], bytes] = {}


def _screenshot_key(ficha: str) -> tuple[str | None, str]:
    """La captura es de un instructor y una ficha: otro instructor no la ve."""
    return (current_instructor.get(), ficha)


# --- Request/Response schemas ---


class ComplaintCandidatesRequest(BaseModel):
    evidence_ids: list[int]
    min_days_inactive: int = 20


class PendingEvidenceInfo(BaseModel):
    item_id: int
    name: str
    category: str


class ComplaintCandidate(BaseModel):
    user_id: int
    full_name: str
    document: str
    email: str
    last_access_days: int
    pending_count: int
    total_selected: int
    pending_evidences: list[PendingEvidenceInfo]


class ComplaintCandidatesResponse(BaseModel):
    ficha: str
    candidates: list[ComplaintCandidate]
    total: int


class ComplaintGenerateRequest(BaseModel):
    user_ids: list[int]
    evidence_ids: list[int]
    coordinator_name: str = ""
    # Nombre de quien firma el informe (el frontend lo toma del perfil del CMM).
    instructor_name: str = Field(min_length=3)
    report_date: str = ""


# --- Helpers ---


def _find_course_by_ficha(snapshot: dict, ficha: str) -> dict:
    """Find course data by ficha. Raises 404 if not found."""
    for c in snapshot.get("courses", []):
        if c["ficha"] == ficha:
            return c
    raise HTTPException(status_code=404, detail=f"Ficha {ficha} not found")


def _find_participants_by_ficha(snapshot: dict, ficha: str) -> list[dict]:
    """Find participants for a ficha."""
    for cp in snapshot.get("participants", []):
        if cp["ficha"] == ficha:
            return cp.get("participants", [])
    return []


# --- Endpoints ---


@router.get(
    "/fichas/{ficha}/complaint-evidences",
    response_model=list[EvidenceItem],
)
def complaint_evidences(
    ficha: str,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Return the list of evidences for a course (for checkbox selection)."""
    course = _find_course_by_ficha(snapshot, ficha)

    result: list[EvidenceItem] = []
    for ev in course.get("evidences", []):
        item_id = ev["item_id"]
        approved = disapproved = pending = 0
        for student in course.get("students", []):
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

        result.append(EvidenceItem(
            item_id=item_id,
            name=ev["name"],
            category=ev["category"],
            total_approved=approved,
            total_disapproved=disapproved,
            total_pending=pending,
        ))

    return result


@router.post(
    "/fichas/{ficha}/complaint-candidates",
    response_model=ComplaintCandidatesResponse,
)
def complaint_candidates(
    ficha: str,
    body: ComplaintCandidatesRequest,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Find students who are inactive and have pending evidences."""
    course = _find_course_by_ficha(snapshot, ficha)
    participants = _find_participants_by_ficha(snapshot, ficha)

    # Build active + inactive participants map
    active_inactive = {}
    for p in participants:
        if p["status"] == "Activo" and p["last_access_days"] >= body.min_days_inactive:
            active_inactive[p["user_id"]] = p

    # Build evidence info lookup
    evidence_info = {}
    for ev in course.get("evidences", []):
        evidence_info[ev["item_id"]] = {
            "name": ev["name"],
            "category": ev["category"],
        }

    candidates: list[ComplaintCandidate] = []

    for student in course.get("students", []):
        if student["user_id"] not in active_inactive:
            continue

        participant = active_inactive[student["user_id"]]

        # Check which selected evidences are pending
        pending_evs: list[PendingEvidenceInfo] = []
        for eid in body.evidence_ids:
            grade = student.get("grades", {}).get(str(eid))
            if grade is None:
                continue
            if grade["value"] == GradeStatus.PENDING.value:
                info = evidence_info.get(eid, {})
                pending_evs.append(PendingEvidenceInfo(
                    item_id=eid,
                    name=info.get("name", f"Evidence {eid}"),
                    category=info.get("category", ""),
                ))

        if not pending_evs:
            continue

        candidates.append(ComplaintCandidate(
            user_id=student["user_id"],
            full_name=student["full_name"],
            document=student["document"],
            email=student["email"],
            last_access_days=participant["last_access_days"],
            pending_count=len(pending_evs),
            total_selected=len(body.evidence_ids),
            pending_evidences=pending_evs,
        ))

    # Sort by pending_count descending
    candidates.sort(key=lambda c: -c.pending_count)

    return ComplaintCandidatesResponse(
        ficha=ficha,
        candidates=candidates,
        total=len(candidates),
    )


@router.post("/fichas/{ficha}/complaint-reports/generate")
def complaint_generate(
    ficha: str,
    body: ComplaintGenerateRequest,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Generate Word complaint reports for selected students. Returns a ZIP."""
    if not body.user_ids:
        raise HTTPException(status_code=400, detail="No students selected")

    course = _find_course_by_ficha(snapshot, ficha)
    participants = _find_participants_by_ficha(snapshot, ficha)

    # Build participant lookup
    participant_map = {p["user_id"]: p for p in participants}

    # Build evidence info lookup
    evidence_info = {}
    for ev in course.get("evidences", []):
        evidence_info[ev["item_id"]] = {
            "name": ev["name"],
            "category": ev["category"],
        }

    # Template path
    from pathlib import Path
    template_path = Path(__file__).resolve().parents[3] / "templates" / "complaint_report_template.docx"
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Complaint report template not found")

    # Load due process records for this ficha
    due_process_data = load_due_process(ficha)
    due_process_records = due_process_data.get("records", {}) if due_process_data else {}

    # Load RAP mapping for competencia descriptions and evidence→RAP lookup
    competencia_descs: dict[str, str] = {}
    evidence_rap_map: dict[str, str] = {}  # GA code → RAP description
    rap_data = load_rap_mapping(ficha)
    if rap_data:
        import re as _re
        _comp_split = _re.compile(r"^(\d+)\s*-\s*(.+)", _re.DOTALL)
        _rap_split = _re.compile(r"^[\d-]+\s*-\s*(.+)", _re.DOTALL)
        for m in rap_data.get("mappings", []):
            # Competencia descriptions
            match = _comp_split.match(m.get("competencia", ""))
            if match:
                code = match.group(1)
                clean_desc = " ".join(match.group(2).split())
                if code not in competencia_descs:
                    competencia_descs[code] = clean_desc
            # Evidence GA code → RAP description
            rap_match = _rap_split.match(m.get("rap", ""))
            if rap_match:
                rap_desc = " ".join(rap_match.group(1).split())
                for ev in m.get("evidencias", []):
                    ga_code = ev.get("code", "")
                    if ga_code:
                        evidence_rap_map[ga_code] = rap_desc

    # Load phone data for this ficha
    phone_data = load_phone_data(ficha)

    # Load and crop participant screenshot if available
    screenshot_images: list[bytes] = []
    screenshot_bytes = _screenshot_store.get(_screenshot_key(ficha))
    if screenshot_bytes:
        try:
            from src.utils.image_cropper import crop_participant_rows
            num_students = len(body.user_ids)
            screenshot_images = crop_participant_rows(screenshot_bytes, num_students)
        except Exception as e:
            logger.warning("Failed to crop participant screenshot: %s", e)

    # Generate one docx per student (sorted alphabetically to match Zajuna order)
    selected_students = [
        s for s in course.get("students", [])
        if s["user_id"] in body.user_ids
    ]
    selected_students.sort(key=lambda s: s["full_name"])

    zip_buffer = io.BytesIO()
    generated = 0
    student_index = 0
    docx_buffers: list[tuple[str, io.BytesIO]] = []

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for student in selected_students:

            # Find pending evidences for this student
            pending_evs = []
            for eid in body.evidence_ids:
                grade = student.get("grades", {}).get(str(eid))
                if grade is None:
                    continue
                if grade["value"] == GradeStatus.PENDING.value:
                    info = evidence_info.get(eid, {})
                    pending_evs.append({
                        "name": info.get("name", f"Evidence {eid}"),
                        "category": info.get("category", ""),
                    })

            if not pending_evs:
                continue

            participant = participant_map.get(student["user_id"], {})

            # Get due process stage
            dp_record = due_process_records.get(str(student["user_id"]))
            dp_stage = dp_record.get("current_stage", "sin_proceso") if dp_record else "sin_proceso"

            # Get phone and participant image for this student
            phone = phone_data.get(student["document"], "")
            participant_image = (
                screenshot_images[student_index]
                if student_index < len(screenshot_images)
                else None
            )

            docx_bytes = generate_complaint_docx(
                template_path=template_path,
                student={
                    "full_name": student["full_name"],
                    "document": student["document"],
                    "email": student["email"],
                    "last_access_days": participant.get("last_access_days", 0),
                },
                ficha=ficha,
                course_name=course["course_name"],
                pending_evidences=pending_evs,
                instructor_name=body.instructor_name.strip().upper(),
                coordinator_name=body.coordinator_name,
                due_process_stage=dp_stage,
                competencia_descriptions=competencia_descs,
                evidence_rap_map=evidence_rap_map,
                phone=phone,
                participant_image=participant_image,
                report_date=body.report_date,
            )

            clean_name = student["full_name"].replace(" ", "_")[:40]
            base_name = f"Informe_Queja_{clean_name}_{student['document']}"
            zf.writestr(f"Word/{base_name}.docx", docx_bytes.getvalue())
            docx_buffers.append((base_name, docx_bytes))
            generated += 1
            student_index += 1

    if generated == 0:
        raise HTTPException(status_code=400, detail="No reports generated")

    # Generate summary txt with student list
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
        lines = [f"LISTADO DE APRENDICES - FICHA {ficha}", ""]
        for i, student in enumerate(selected_students, 1):
            participant = participant_map.get(student["user_id"], {})
            days = participant.get("last_access_days", 0)
            lines.append(
                f"{i}. {student['full_name']} - CC {student['document']} - "
                f"{days} días sin conectarse"
            )
        zf.writestr("listado_aprendices.txt", "\n".join(lines))

    # Convert docx to PDF and add to ZIP
    _convert_and_add_pdfs(zip_buffer, docx_buffers)

    zip_buffer.seek(0)
    date_str = datetime.now().strftime("%Y%m%d")
    zip_name = f"Informes_Queja_{ficha}_{date_str}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


def _convert_and_add_pdfs(
    zip_buffer: io.BytesIO,
    docx_buffers: list[tuple[str, io.BytesIO]],
) -> None:
    """Convert docx buffers to PDF using docx2pdf and add them to the ZIP.

    Uses a temp directory to write .docx files, converts them with docx2pdf,
    and appends the resulting PDFs to the already-open ZIP.
    """
    if not docx_buffers:
        return

    try:
        from docx2pdf import convert
    except ImportError:
        logger.warning("docx2pdf not installed — skipping PDF generation")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        docx_dir = tmp_path / "docx"
        pdf_dir = tmp_path / "pdf"
        docx_dir.mkdir()
        pdf_dir.mkdir()

        # Write all docx files to temp directory
        for base_name, buf in docx_buffers:
            docx_file = docx_dir / f"{base_name}.docx"
            docx_file.write_bytes(buf.getvalue())

        # Batch convert entire directory (COM needs CoInitialize in worker threads)
        try:
            import sys
            if sys.platform == "win32":
                import pythoncom
                pythoncom.CoInitialize()
            try:
                convert(str(docx_dir), str(pdf_dir))
            finally:
                if sys.platform == "win32":
                    pythoncom.CoUninitialize()
        except Exception as e:
            logger.error("PDF conversion failed: %s", e)
            return

        # Add PDFs to the existing ZIP
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
            for pdf_file in sorted(pdf_dir.glob("*.pdf")):
                zf.writestr(f"PDF/{pdf_file.name}", pdf_file.read_bytes())

    logger.info("Added %d PDF files to ZIP", len(docx_buffers))


# --- Phone data endpoints ---


class PhoneImportRequest(BaseModel):
    folder_path: str


class PhoneImportResponse(BaseModel):
    imported: dict[str, int]


@router.post("/fichas/phone-data/import", response_model=PhoneImportResponse)
def import_phone_data(
    body: PhoneImportRequest,
    _key: str = Depends(verify_api_key),
    snapshot: dict = Depends(get_snapshot),
):
    """Import phone data from Excel files in a folder.

    Lee una carpeta de la máquina del servidor: solo existe como herramienta
    local (LOCAL_TOOLS_ENABLED) y solo guarda las fichas del instructor.
    """
    from scripts.import_phone_data import import_folder

    if not get_security_settings().local_tools:
        raise HTTPException(status_code=404, detail="No disponible en este servidor")
    fichas = {c.get("ficha") for c in snapshot.get("courses", [])}
    try:
        results = import_folder(body.folder_path, allowed_fichas=fichas)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="No se encontró la carpeta") from e
    except Exception as e:
        logger.exception("Falló la importación de teléfonos")
        raise HTTPException(status_code=500, detail="No se pudieron importar los teléfonos") from e

    return PhoneImportResponse(imported=results)


@router.get("/fichas/{ficha}/phone-data")
def get_phone_data(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Get phone data for a ficha."""
    data = load_phone_data(ficha)
    return {"ficha": ficha, "count": len(data), "phones": data}


# --- Participant screenshot endpoints ---


@router.post("/fichas/{ficha}/participant-screenshot")
async def upload_participant_screenshot(
    ficha: str,
    file: UploadFile = File(...),
    _key: str = Depends(verify_api_key),
):
    """Upload a participant screenshot for a ficha. Used during report generation."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    _screenshot_store[_screenshot_key(ficha)] = content
    logger.info("Stored participant screenshot for ficha %s: %d bytes", ficha, len(content))
    return {"ficha": ficha, "size": len(content), "filename": file.filename}


@router.delete("/fichas/{ficha}/participant-screenshot")
def delete_participant_screenshot(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Remove stored participant screenshot."""
    _screenshot_store.pop(_screenshot_key(ficha), None)
    return {"ficha": ficha, "deleted": True}
