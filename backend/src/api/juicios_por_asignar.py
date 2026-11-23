"""Juicios por asignar en Sofía Plus: a quién aprobar y a quién no, por competencia y RAP.

Sofía Plus permite cargar juicios en grupo (marcar aprendices, elegir
competencia y RAP, y asignar un valor). Esto arma esas dos listas a partir del
cruce Zajuna ↔ Sofía, solo con aprendices EN FORMACIÓN en Sofía, sin novedad
registrada, no suspendidos en Zajuna y con el juicio POR EVALUAR:

- **Aprobar**: todas las evidencias del RAP aprobadas (A) en Zajuna.
- **No aprobar**: alguna evidencia del RAP con D, o alguna evidencia sin nota
  entre las que el instructor eligió hasta su corte (la misma selección de
  Reportes): ya debía estar entregada.
"""
from __future__ import annotations

import re
import unicodedata

from src.api.rap_cross_engine import _build_competency_bridge, _find_sofia_judgment
from src.models.schemas import GradeStatus

EN_FORMACION = "EN FORMACION"


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper().strip()


_CODE_PREFIX = re.compile(r"^\s*(\d{6,9}(?:-\d{2,3})?)\s*-\s*(.*)$", re.DOTALL)


def _split_code(text: str) -> tuple[str, str]:
    """"220501092 - Establecer…" o "220501097- Implementar…" → (código, descripción)."""
    m = _CODE_PREFIX.match(text or "")
    return (m.group(1), m.group(2).strip()) if m else ("", (text or "").strip())


def _evidence_counts(grades: dict, evidencias: list[dict], hasta_corte: set[int]) -> dict[str, int]:
    counts = {"total": 0, "aprobadas": 0, "desaprobadas": 0, "sin_entregar": 0, "fuera_de_corte": 0}
    for ev in evidencias:
        item_id = ev.get("item_id")
        if item_id is None:
            continue
        counts["total"] += 1
        value = (grades.get(str(item_id)) or {}).get("value", "-")
        if value == GradeStatus.APPROVED.value:
            counts["aprobadas"] += 1
        elif value == GradeStatus.DISAPPROVED.value:
            counts["desaprobadas"] += 1
        elif item_id in hasta_corte:
            counts["sin_entregar"] += 1
        else:
            counts["fuera_de_corte"] += 1
    return counts


def compute_juicios_por_asignar(
    snapshot: dict,
    ficha: str,
    rap_mapping: dict,
    sofia_report: dict,
    evidence_ids: set[int],
    novedad_ids: set[int] | None = None,
) -> dict:
    """``evidence_ids``: evidencias elegidas hasta el corte; sin nota cuentan como no entregadas.

    ``novedad_ids``: user_id con novedad registrada (cancelación, retiro, traslado…).
    """
    empty = {"ficha": ficha, "aprobar": [], "no_aprobar": [], "fuera_de_formacion": 0, "con_novedad": 0, "suspendidos": 0}
    course = next((c for c in snapshot.get("courses", []) if c.get("ficha") == ficha), None)
    if course is None:
        return empty

    students = course.get("students", [])
    grades_by_doc = {s["document"]: s.get("grades", {}) for s in students}
    uid_by_doc = {s["document"]: s["user_id"] for s in students}
    # Suspendidos según la página de participantes de Zajuna (como en Debido proceso).
    suspended = {
        p["user_id"]
        for cp in snapshot.get("participants", [])
        if cp.get("course_id") == course.get("course_id")
        for p in cp.get("participants", [])
        if p.get("status") == "Suspendido"
    }
    novedad_ids = novedad_ids or set()
    bridge = _build_competency_bridge(rap_mapping, sofia_report)

    # Textos de Sofía (código y descripción) de cada RAP, tal como aparecen allá.
    sofia_raps: dict[str, dict] = {}
    for st in sofia_report.get("students", []):
        for j in st.get("judgments", []):
            if j.get("rap_code"):
                sofia_raps.setdefault(j["rap_code"], j)

    en_formacion = []
    fuera = con_novedad = suspendidos = 0
    for st in sofia_report.get("students", []):
        uid = uid_by_doc.get(st["document"])
        if uid is None:
            continue
        if _fold(st.get("student_status") or EN_FORMACION) != EN_FORMACION:
            fuera += 1
        elif uid in novedad_ids:
            con_novedad += 1
        elif uid in suspended:
            suspendidos += 1
        else:
            en_formacion.append(st)

    groups: dict[str, dict[tuple, dict]] = {"aprobar": {}, "no_aprobar": {}}
    for m in rap_mapping.get("mappings", []):
        evidencias = m.get("evidencias", [])
        code = m.get("rap_sofia_code") or ""
        sofia = sofia_raps.get(code, {})
        prog_comp_code, prog_comp_desc = _split_code(m["competencia"])
        prog_rap_code, prog_rap_desc = _split_code(m["rap"])
        rap_info = {
            "competencia_code": sofia.get("competencia_code") or prog_comp_code,
            "competencia_desc": sofia.get("competencia_desc") or prog_comp_desc,
            "competencia_programa": prog_comp_code,
            "rap_code": code or prog_rap_code,
            "rap_desc": sofia.get("rap_desc") or prog_rap_desc,
            "rap_programa": prog_rap_code,
            "fase": m.get("fase", ""),
        }
        for st in en_formacion:
            judgments = st.get("judgments", [])
            juicio = next((j.get("juicio") for j in judgments if code and j.get("rap_code") == code), None)
            if juicio is None:
                juicio = _find_sofia_judgment(judgments, m["rap"], m["competencia"], bridge)
            if _fold(juicio or "POR EVALUAR") != "POR EVALUAR":
                continue
            counts = _evidence_counts(grades_by_doc[st["document"]], evidencias, evidence_ids)
            if counts["total"] == 0:
                continue
            if counts["aprobadas"] == counts["total"]:
                target = "aprobar"
            elif counts["desaprobadas"] or counts["sin_entregar"]:
                target = "no_aprobar"
            else:
                continue
            key = (rap_info["competencia_programa"], rap_info["rap_programa"], rap_info["rap_code"])
            entry = groups[target].setdefault(key, {**rap_info, "aprendices": []})
            entry["aprendices"].append({"document": st["document"], "full_name": st["full_name"], **counts})

    def ordered(target: str) -> list[dict]:
        out = []
        for key in sorted(groups[target]):
            entry = groups[target][key]
            entry["aprendices"].sort(key=lambda a: _fold(a["full_name"]))
            out.append(entry)
        return out

    return {
        "ficha": ficha,
        "aprobar": ordered("aprobar"),
        "no_aprobar": ordered("no_aprobar"),
        "fuera_de_formacion": fuera,
        "con_novedad": con_novedad,
        "suspendidos": suspendidos,
    }
