"""RAP cross-reference engine: match Zajuna grades against Sofia Plus judgments."""
from __future__ import annotations

import re

from src.models.schemas import GradeStatus

# Regex to extract SENA evidence code from evidence names
EVIDENCE_CODE_RE = re.compile(r"(GA\d+-\d{6,9}-AA\d+-EV\d+)")


def _normalize_desc(desc: str) -> str:
    """Normalize a competency description for fuzzy matching.

    Strips leading codes/numbers, collapses whitespace (Excel cells may
    contain newlines), and lowercases.
    """
    # Remove leading code like "220501092 - " or "38392 - "
    cleaned = re.sub(r"^\d+\s*[-–]\s*", "", desc)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _build_competency_bridge(rap_mapping: dict, sofia_report: dict) -> dict[str, str]:
    """Build a mapping from Sofia competency keys to Zajuna competency descriptions.

    Uses the competency_map from sofia_report if it contains explicit mappings,
    then falls back to description-based fuzzy matching.
    """
    bridge = {}

    # Use explicit competency_map if values differ from keys (manual mapping)
    comp_map = sofia_report.get("competency_map", {})
    for sofia_key, zajuna_key in comp_map.items():
        if sofia_key != zajuna_key:
            bridge[sofia_key] = zajuna_key

    # If bridge is empty or incomplete, build by matching descriptions
    if not bridge:
        # Collect all unique Zajuna competencies from RAP mapping
        zajuna_comps: dict[str, str] = {}  # normalized_desc → full competency string
        for m in rap_mapping.get("mappings", []):
            comp = m.get("competencia", "")
            if comp:
                zajuna_comps[_normalize_desc(comp)] = comp

        # Collect all unique Sofia competencies from student judgments
        sofia_comp_keys = set()
        for student in sofia_report.get("students", []):
            for j in student.get("judgments", []):
                code = j.get("competencia_code", "")
                desc = j.get("competencia_desc", "")
                if code and desc:
                    sofia_comp_keys.add(f"{code} - {desc}")
                elif desc:
                    sofia_comp_keys.add(desc)

        # Match by normalized description
        for sofia_key in sofia_comp_keys:
            sofia_norm = _normalize_desc(sofia_key)
            # Try exact match first
            if sofia_norm in zajuna_comps:
                bridge[sofia_key] = zajuna_comps[sofia_norm]
                continue
            # Try substring match (Sofia desc starts with Zajuna desc or vice versa)
            for zajuna_norm, zajuna_full in zajuna_comps.items():
                if sofia_norm.startswith(zajuna_norm[:40]) or zajuna_norm.startswith(sofia_norm[:40]):
                    bridge[sofia_key] = zajuna_full
                    break

    return bridge


def _get_zajuna_evidence_status(
    student_grades: dict,
    evidencias: list[dict],
) -> tuple[str, int, int]:
    """Determine the Zajuna status for a RAP based on its evidence grades.

    Returns: (status, total_evidencias, aprobadas)
    Status: "todas_aprobadas", "alguna_pendiente", "alguna_desaprobada"
    """
    total = 0
    aprobadas = 0
    has_desaprobada = False

    for ev in evidencias:
        item_id = ev.get("item_id")
        if item_id is None:
            continue
        total += 1

        grade = student_grades.get(str(item_id))
        if grade is None:
            continue

        value = grade.get("value", "-")
        if value == GradeStatus.APPROVED.value:
            aprobadas += 1
        elif value == GradeStatus.DISAPPROVED.value:
            has_desaprobada = True

    if total == 0:
        return "alguna_pendiente", 0, 0

    if aprobadas == total:
        return "todas_aprobadas", total, aprobadas

    if has_desaprobada:
        return "alguna_desaprobada", total, aprobadas

    return "alguna_pendiente", total, aprobadas


def _compute_resultado(zajuna_status: str, sofia_juicio: str) -> str:
    """Compute the cross-reference result based on the status matrix.

    | Zajuna (evidencias) | Sofia (juicio) | Resultado           |
    |---------------------|----------------|---------------------|
    | todas_aprobadas     | POR EVALUAR    | listo_para_aprobar  |
    | todas_aprobadas     | APROBADO       | correcto            |
    | alguna_pendiente    | POR EVALUAR    | pendiente           |
    | alguna_desaprobada  | POR EVALUAR    | con_problemas       |
    | todas_aprobadas     | NO APROBADO    | inconsistencia      |
    | alguna_pend/desap   | APROBADO       | aprobado_anticipado |
    """
    juicio_upper = sofia_juicio.upper().strip()

    if zajuna_status == "todas_aprobadas":
        return {
            "POR EVALUAR": "listo_para_aprobar",
            "APROBADO": "correcto",
            "NO APROBADO": "inconsistencia",
        }.get(juicio_upper, "pendiente")

    if zajuna_status in ("alguna_pendiente", "alguna_desaprobada"):
        if juicio_upper == "APROBADO":
            return "aprobado_anticipado"
        if zajuna_status == "alguna_desaprobada":
            return "con_problemas"
        return "pendiente"

    return "pendiente"


def _extract_rap_number(rap_str: str) -> str | None:
    """Extract the RAP sequence number from various formats.

    Zajuna: "220501092-01 - INTERPRETAR" → "01"
    Sofia:  "01 INTERPRETAR" or "01 DEFINIR LAS CARACTERÍSTICAS" → "01"
    """
    # Try Zajuna format: "CODE-NN - DESC" (also "CODE-NN" without description)
    m = re.search(r"\d{9}\s*-\s*(\d{2,3})(?:\s*-|\s|$)", rap_str)
    if m:
        return m.group(1).lstrip("0") or "0"

    # Try Sofia format: "NN DESC" or "NN- DESC" (number at start)
    m = re.match(r"(\d{2,3})\s*-?\s", rap_str.strip())
    if m:
        return m.group(1).lstrip("0") or "0"

    return None


def _find_sofia_judgment(
    student_judgments: list[dict],
    rap_zajuna: str,
    competencia_zajuna: str,
    bridge: dict[str, str],
) -> str | None:
    """Find the Sofia judgment for a given Zajuna RAP.

    Matches by finding the Sofia competency that maps to the same Zajuna competency,
    then finding the RAP within it by RAP sequence number.
    """
    zajuna_comp_norm = _normalize_desc(competencia_zajuna)
    zajuna_rap_num = _extract_rap_number(rap_zajuna)

    for j in student_judgments:
        # Build Sofia competency key (may or may not have code)
        code = j.get("competencia_code", "")
        desc = j.get("competencia_desc", "")
        sofia_comp_key = f"{code} - {desc}" if code else desc

        # Try bridge lookup first
        mapped_zajuna = bridge.get(sofia_comp_key, "")

        # Fallback: direct description comparison
        if not mapped_zajuna:
            sofia_desc_norm = _normalize_desc(desc)
            if sofia_desc_norm and (
                sofia_desc_norm == zajuna_comp_norm
                or sofia_desc_norm.startswith(zajuna_comp_norm[:40])
                or zajuna_comp_norm.startswith(sofia_desc_norm[:40])
            ):
                mapped_zajuna = competencia_zajuna

        if mapped_zajuna:
            mapped_norm = _normalize_desc(mapped_zajuna)
            if mapped_norm == zajuna_comp_norm:
                sofia_rap_num = _extract_rap_number(j.get("rap_desc", ""))

                if zajuna_rap_num and sofia_rap_num and zajuna_rap_num == sofia_rap_num:
                    return j.get("juicio", "POR EVALUAR")

    return None


def compute_rap_cross(
    snapshot: dict,
    ficha: str,
    rap_mapping: dict,
    sofia_report: dict,
    filter_resultado: str | None = None,
    filter_document: str | None = None,
) -> dict:
    """Compute the full RAP cross-reference for a ficha.

    Args:
        snapshot: Zajuna grader snapshot (from latest.json)
        ficha: Ficha number
        rap_mapping: Stored RAP mapping (from rap_mapping_store)
        sofia_report: Stored Sofia report (from sofia_store)
        filter_resultado: Optional filter by resultado type
        filter_document: Optional filter by student document

    Returns a dict with students, their RAP cross results, and summary.
    """
    # Find course in snapshot
    course = None
    for c in snapshot.get("courses", []):
        if c.get("ficha") == ficha:
            course = c
            break

    if course is None:
        return {
            "ficha": ficha,
            "total_students": 0,
            "total_raps": 0,
            "students": [],
            "summary": {},
        }

    # Build grade lookup: {user_id: {item_id_str: grade}}
    grade_lookup = {}
    student_info = {}
    for s in course.get("students", []):
        uid = s["user_id"]
        grade_lookup[uid] = s.get("grades", {})
        student_info[uid] = {
            "full_name": s["full_name"],
            "document": s["document"],
            "status": s.get("status", "Activo"),
        }

    # Build document→user_id lookup
    doc_to_uid = {}
    for uid, info in student_info.items():
        doc = info["document"]
        doc_to_uid[doc] = uid

    # Build competency bridge
    bridge = _build_competency_bridge(rap_mapping, sofia_report)

    mappings = rap_mapping.get("mappings", [])

    # Summary counters
    summary = {
        "listo_para_aprobar": 0,
        "correcto": 0,
        "pendiente": 0,
        "con_problemas": 0,
        "inconsistencia": 0,
        "aprobado_anticipado": 0,
    }

    results = []

    for sofia_student in sofia_report.get("students", []):
        doc = sofia_student["document"]

        if filter_document and doc != filter_document:
            continue

        uid = doc_to_uid.get(doc)
        if uid is None:
            continue

        student_grades = grade_lookup.get(uid, {})
        student_judgments = sofia_student.get("judgments", [])

        # Exact lookup by Sofia RAP code (6 digits) — the code is unique
        # across the whole program, so no competency bridging is needed.
        judgment_by_code = {
            j["rap_code"]: j.get("juicio", "POR EVALUAR")
            for j in student_judgments
            if j.get("rap_code")
        }

        raps_results = []

        for mapping in mappings:
            rap_desc = mapping["rap"]
            competencia = mapping["competencia"]
            evidencias = mapping.get("evidencias", [])

            # Get Zajuna status
            zajuna_status, ev_total, ev_aprobadas = _get_zajuna_evidence_status(
                student_grades, evidencias
            )

            # Get Sofia judgment: exact by code, fuzzy fallback for
            # mappings saved before rap_sofia_code existed.
            sofia_juicio = judgment_by_code.get(mapping.get("rap_sofia_code") or "")
            if sofia_juicio is None:
                sofia_juicio = _find_sofia_judgment(
                    student_judgments, rap_desc, competencia, bridge
                )

            if sofia_juicio is None:
                sofia_juicio = "POR EVALUAR"

            resultado = _compute_resultado(zajuna_status, sofia_juicio)

            if filter_resultado and resultado != filter_resultado:
                continue

            summary[resultado] = summary.get(resultado, 0) + 1

            raps_results.append({
                "rap": rap_desc,
                "competencia": competencia,
                "zajuna_status": zajuna_status,
                "sofia_juicio": sofia_juicio,
                "resultado": resultado,
                "evidencias_total": ev_total,
                "evidencias_aprobadas": ev_aprobadas,
            })

        if not raps_results and filter_resultado:
            continue

        # Count by resultado
        counts = {}
        for r in raps_results:
            counts[r["resultado"]] = counts.get(r["resultado"], 0) + 1

        # Get enrollment status from Zajuna data
        zajuna_info = student_info.get(uid, {}) if uid else {}
        enrollment_status = zajuna_info.get("status", "Activo")

        results.append({
            "document": doc,
            "full_name": sofia_student["full_name"],
            "status": enrollment_status,
            "raps": raps_results,
            "total_raps": len(raps_results),
            "listos_para_aprobar": counts.get("listo_para_aprobar", 0),
            "correctos": counts.get("correcto", 0),
            "pendientes": counts.get("pendiente", 0),
            "con_problemas": counts.get("con_problemas", 0),
            "inconsistencias": counts.get("inconsistencia", 0),
            "aprobados_anticipados": counts.get("aprobado_anticipado", 0),
        })

    return {
        "ficha": ficha,
        "total_students": len(results),
        "total_raps": len(mappings),
        "students": results,
        "summary": summary,
    }
