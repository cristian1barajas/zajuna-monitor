"""Generate complaint report Word documents from template."""
from __future__ import annotations

import io
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt

# --- Competencia code extraction ---

_GA_PATTERN = re.compile(r"GA\d+-\s*(\d+)-")
_GA_FULL_PATTERN = re.compile(r"(GA\d+-\d+-AA\d+-EV\d+)")
_FASE_NUMBER = re.compile(r"^(Fase)\s+\d+\s+", re.IGNORECASE)
_FICHA_SUFFIX = re.compile(r"\s*\(\d+\)\s*$")


def _extract_competencia_code(evidence_name: str) -> str:
    """Extract competencia code from evidence GA code pattern."""
    m = _GA_PATTERN.search(evidence_name)
    return m.group(1) if m else ""


def _extract_ga_code(evidence_name: str) -> str:
    """Extract full GA code (e.g. GA1-220501092-AA1-EV01) from evidence name."""
    m = _GA_FULL_PATTERN.search(evidence_name)
    return m.group(1) if m else ""


def _strip_fase_number(fase: str) -> str:
    """Strip the number from 'Fase 2 Planeación' → 'Fase Planeación'."""
    return _FASE_NUMBER.sub(r"\1 ", fase)


def _strip_ficha_from_course(course_name: str) -> str:
    """Strip ficha code suffix from course name: 'ADSO. (2977396)' → 'ADSO.'."""
    return _FICHA_SUFFIX.sub("", course_name)


# --- Due process stage descriptions ---

_DUE_PROCESS_DESCRIPTIONS = {
    "sin_proceso": (
        "Siguiendo el debido proceso indicado en el Reglamento del Aprendiz SENA, "
        "se ha efectuado llamado de atención verbal al aprendiz, como medida "
        "formativa con el fin de generar cambios en el desempeño académico "
        "y/o disciplinario."
    ),
    "primer_llamado": (
        "Siguiendo el debido proceso indicado en el Reglamento del Aprendiz SENA, "
        "se ha efectuado llamado de atención verbal al aprendiz, como medida "
        "formativa con el fin de generar cambios en el desempeño académico "
        "y/o disciplinario.     SI    _X_        NO   ______"
    ),
    "segundo_llamado": (
        "Siguiendo el debido proceso indicado en el Reglamento del Aprendiz SENA, "
        "se ha efectuado primer llamado de atención escrito y segundo llamado de "
        "atención verbal al aprendiz.     SI    _X_        NO   ______"
    ),
    "plan_mejoramiento": (
        "Siguiendo el debido proceso indicado en el Reglamento del Aprendiz SENA, "
        "se han efectuado primer y segundo llamados de atención, y se ha asignado "
        "un plan de mejoramiento al aprendiz.     SI    _X_        NO   ______"
    ),
    "comite": (
        "Siguiendo el debido proceso indicado en el Reglamento del Aprendiz SENA, "
        "se han agotado todas las instancias previas (llamados de atención y plan "
        "de mejoramiento). Se remite al Comité de Evaluación."
    ),
}


def generate_complaint_docx(
    template_path: Path,
    student: dict,
    ficha: str,
    course_name: str,
    pending_evidences: list[dict],
    instructor_name: str,
    coordinator_name: str,
    due_process_stage: str = "sin_proceso",
    competencia_descriptions: dict[str, str] | None = None,
    evidence_rap_map: dict[str, str] | None = None,
    phone: str = "",
    participant_image: bytes | None = None,
    report_date: str = "",
) -> io.BytesIO:
    """Fill the complaint report template with student data.

    Args:
        template_path: Path to the .docx template
        student: dict with full_name, document, email, last_access_days
        ficha: Ficha number
        course_name: Name of the training program
        pending_evidences: list of dicts with name, category
        instructor_name: Name of the instructor
        coordinator_name: Name of the coordinator
        due_process_stage: Current due process stage for this student
        competencia_descriptions: Optional code→description map from RAP mapping

    Returns:
        BytesIO with the filled .docx
    """
    comp_descs = competencia_descriptions or {}
    rap_map = evidence_rap_map or {}

    doc = Document(str(template_path))
    table0 = doc.tables[0]
    table1 = doc.tables[1]
    rows = table1.rows

    # --- Table 0: Header ---
    table0.rows[0].cells[1].text = coordinator_name
    table0.rows[1].cells[3].text = report_date or datetime.now().strftime("%d-%m-%Y")

    # --- Table 1: Student info ---
    _set_cell_text(rows, 0, 1, student["full_name"])
    _set_cell_text(rows, 1, 1, student["document"])
    _set_cell_text(rows, 2, 1, phone)
    _set_cell_text(rows, 3, 1, student["email"])
    # Program name without ficha code (ficha already in No. de Ficha column)
    _set_cell_text(rows, 4, 1, _strip_ficha_from_course(course_name))
    _set_cell_text(rows, 4, 4, ficha)

    # --- Row 5: Competencias (with descriptions) + Fase ---
    competencia_parts, fase = _extract_competencia_info(pending_evidences, comp_descs)
    _fill_competencia_cell(rows[5].cells[1], competencia_parts)
    _set_cell_text(rows, 5, 4, _strip_fase_number(fase))

    # --- Row 6: Due process message ---
    _fill_due_process_cell(rows[6].cells[0], due_process_stage)

    # --- Row 7: Narrative with evidences ---
    _fill_narrative_cell(
        rows[7].cells[0],
        student=student,
        course_name=course_name,
        ficha=ficha,
        pending_evidences=pending_evidences,
        due_process_stage=due_process_stage,
        rap_map=rap_map,
    )

    # Insert participant screenshot if provided
    if participant_image:
        _insert_participant_image(rows[7].cells[0], participant_image)

    # Write to buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def _set_cell_text(rows, row_idx: int, col_idx: int, text: str) -> None:
    """Safely set cell text in a table."""
    if row_idx < len(rows) and col_idx < len(rows[row_idx].cells):
        rows[row_idx].cells[col_idx].text = text


def _extract_competencia_info(
    pending_evidences: list[dict],
    comp_descs: dict[str, str] | None = None,
) -> tuple[list[str], str]:
    """Extract competencia codes (with descriptions) and fase from evidences.

    Returns (list of competencia strings, fase_text).
    """
    descs = comp_descs or {}
    codes: OrderedDict[str, None] = OrderedDict()
    fase = ""

    for ev in pending_evidences:
        code = _extract_competencia_code(ev.get("name", ""))
        if code:
            codes[code] = None
        if not fase and ev.get("category"):
            fase = ev["category"]

    # Build list: "CODE - description" if description available, else just code
    parts: list[str] = []
    for code in codes:
        desc = descs.get(code)
        if desc:
            parts.append(f"{code} - {desc}")
        else:
            parts.append(code)

    return parts, fase


def _fill_competencia_cell(cell, parts: list[str]) -> None:
    """Fill the competencia cell with one line per competencia."""
    cell.text = ""  # Clear
    if not parts:
        return
    # First competencia in the existing paragraph
    p = cell.paragraphs[0]
    p.clear()
    run = p.add_run(parts[0])
    run.font.size = Pt(10)
    # Additional competencias as new paragraphs
    for part in parts[1:]:
        np = cell.add_paragraph()
        run = np.add_run(part)
        run.font.size = Pt(10)


def _fill_due_process_cell(cell, stage: str) -> None:
    """Fill the due process row with the appropriate message."""
    # Clear existing content
    for p in cell.paragraphs:
        for run in p.runs:
            run.text = ""

    desc = _DUE_PROCESS_DESCRIPTIONS.get(stage, _DUE_PROCESS_DESCRIPTIONS["sin_proceso"])

    # Set the first paragraph text
    if cell.paragraphs:
        p = cell.paragraphs[0]
        p.clear()
        run = p.add_run(desc)
        run.font.size = Pt(10)

        # Add the title in bold on a new line
        if len(cell.paragraphs) > 1:
            p2 = cell.paragraphs[1]
            p2.clear()
        else:
            p2 = cell.add_paragraph()
        title_run = p2.add_run(
            "INFORME O QUEJA y REPORTE DE SEGUIMIENTO POR PARTE DEL INSTRUCTOR"
        )
        title_run.bold = True
        title_run.underline = True
        title_run.font.size = Pt(10)


def _clear_cell(cell) -> None:
    """Remove all paragraphs from a cell except the first (required by docx)."""
    tc = cell._tc
    # Remove all <w:p> elements except the first
    ps = tc.findall(
        ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
    )
    for p in ps[1:]:
        tc.remove(p)
    # Clear the first paragraph
    if cell.paragraphs:
        cell.paragraphs[0].clear()


def _fill_narrative_cell(
    cell,
    student: dict,
    course_name: str,
    ficha: str,
    pending_evidences: list[dict],
    due_process_stage: str,
    rap_map: dict[str, str] | None = None,
) -> None:
    """Fill the narrative cell with formatted evidence listing."""
    rap_lookup = rap_map or {}

    # Remove all existing paragraphs (eliminates blank space)
    _clear_cell(cell)

    # Group evidences by category, tracking RAP per evidence
    by_category: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()
    for ev in pending_evidences:
        category = ev.get("category", "Sin categoría")
        if category not in by_category:
            by_category[category] = []
        name = ev["name"]
        ga_code = _extract_ga_code(name)
        rap_desc = rap_lookup.get(ga_code, "")
        by_category[category].append((name, rap_desc))

    days = student.get("last_access_days", 0)

    # Start with intro text (reuse the remaining first paragraph)
    first_p = cell.paragraphs[0]
    intro = first_p.add_run(
        "El aprendiz mencionado en este informe, como responsable principal "
        "de su proceso de formación, no entregó puntualmente las evidencias "
        "que se detallan a continuación:"
    )
    intro.font.size = Pt(10)

    # Blank line after intro
    cell.add_paragraph()

    # Add evidences grouped by category with RAP
    for category, items in by_category.items():
        # Competencia header
        p = cell.add_paragraph()
        label = p.add_run("Competencia: ")
        label.bold = True
        label.font.size = Pt(10)
        value = p.add_run(category)
        value.font.size = Pt(10)

        # Track RAPs already printed for this category to avoid repeats
        printed_raps: set[str] = set()

        for name, rap_desc in items:
            # RAP line (only once per unique RAP within this category)
            rap_key = rap_desc.rstrip(".").lower() if rap_desc else ""
            if rap_desc and rap_key not in printed_raps:
                printed_raps.add(rap_key)
                rp = cell.add_paragraph()
                rlabel = rp.add_run("Resultado de Aprendizaje: ")
                rlabel.bold = True
                rlabel.font.size = Pt(10)
                rvalue = rp.add_run(rap_desc)
                rvalue.font.size = Pt(10)

            # Evidence line
            ep = cell.add_paragraph()
            elabel = ep.add_run("Evidencia: ")
            elabel.bold = True
            elabel.font.size = Pt(10)
            evalue = ep.add_run(name)
            evalue.font.size = Pt(10)

    # Blank line before closing
    cell.add_paragraph()

    # Closing paragraph with due process context
    closing_p = cell.add_paragraph()
    closing_text = _build_closing_text(
        student_name=student["full_name"],
        days_inactive=days,
        due_process_stage=due_process_stage,
    )
    closing_run = closing_p.add_run(closing_text)
    closing_run.font.size = Pt(10)


def _build_closing_text(
    student_name: str,
    days_inactive: int,
    due_process_stage: str,
) -> str:
    """Build the closing narrative based on due process stage."""
    base = (
        f"Además, el aprendiz registra último acceso al LMS Zajuna hace más de "
        f"{days_inactive} días."
    )

    if due_process_stage in ("sin_proceso", "primer_llamado"):
        return (
            f"{base} En virtud de lo anterior, el equipo ejecutor solicita al "
            f"centro de formación la cancelación de su registro de matrícula "
            f"ya que por tiempo no es posible presentar todas las actividades "
            f"pendientes."
        )
    elif due_process_stage == "segundo_llamado":
        return (
            f"{base} Se han realizado dos llamados de atención previos sin "
            f"obtener respuesta ni mejora por parte del aprendiz. Se solicita "
            f"asignación de plan de mejoramiento."
        )
    elif due_process_stage == "plan_mejoramiento":
        return (
            f"{base} Se han agotado los llamados de atención y el plan de "
            f"mejoramiento sin que el aprendiz haya cumplido con las "
            f"actividades requeridas. Se solicita remisión al Comité de "
            f"Evaluación y Seguimiento."
        )
    else:
        return (
            f"{base} Se solicita dar inicio al proceso académico "
            f"correspondiente según el Reglamento del Aprendiz SENA."
        )


def _insert_participant_image(cell, image_bytes: bytes) -> None:
    """Insert a participant screenshot image at the end of a cell."""
    img_stream = io.BytesIO(image_bytes)
    p = cell.add_paragraph()
    run = p.add_run()
    run.add_picture(img_stream, width=Inches(6.5))
