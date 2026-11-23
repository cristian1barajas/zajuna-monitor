"""Estadísticas de curso calculadas solo sobre aprendices activos.

Un aprendiz suspendido conserva sus celdas "pendiente" en el grader, pero
no tiene sentido contarlas: infla los pendientes y hunde el % de avance.
Estas funciones recomputan las métricas ignorando a los suspendidos,
usando el estado que viene de la página de participantes.

Fuente única de verdad: dashboard, lista de fichas y detalle la usan por
igual para que los números sean consistentes en toda la app.
"""
from __future__ import annotations

from src.models.schemas import GradeStatus

APPROVED = GradeStatus.APPROVED.value
DISAPPROVED = GradeStatus.DISAPPROVED.value
PENDING = GradeStatus.PENDING.value


def build_active_ids(participants_list: list[dict]) -> dict[int, set[int]]:
    """course_id -> conjunto de user_ids con matrícula activa."""
    result: dict[int, set[int]] = {}
    for cp in participants_list:
        course_id = cp.get("course_id")
        if course_id is None:
            continue
        result[course_id] = {
            p["user_id"]
            for p in cp.get("participants", [])
            if p.get("status") == "Activo"
        }
    return result


def compute_active_stats(course_data: dict, active_ids: set[int]) -> dict:
    """Recuenta aprobadas/desaprobadas/pendientes solo de aprendices activos.

    Devuelve dict con: active_students, approved, disapproved, pending,
    completion_percentage.
    """
    approved = disapproved = pending = active_count = 0

    for student in course_data.get("students", []):
        if student["user_id"] not in active_ids:
            continue
        active_count += 1
        for grade in student.get("grades", {}).values():
            value = grade["value"] if isinstance(grade, dict) else grade.value
            if value == APPROVED:
                approved += 1
            elif value == DISAPPROVED:
                disapproved += 1
            elif value == PENDING:
                pending += 1

    cells = approved + disapproved + pending
    completion = round((approved + disapproved) / cells * 100, 1) if cells else 0.0

    return {
        "active_students": active_count,
        "approved": approved,
        "disapproved": disapproved,
        "pending": pending,
        "cells": cells,
        "completion_percentage": completion,
    }


def resolve_stats(course_data: dict | None, active_ids: set[int] | None, summary: dict) -> dict:
    """Estadísticas por activos, con fallback al summary crudo.

    Si no hay datos de participantes para el curso (p. ej. el scrape de
    participantes falló), cae al summary completo para no mostrar ceros.
    """
    if course_data is not None and active_ids is not None:
        return compute_active_stats(course_data, active_ids)
    cells = (
        summary.get("total_approved", 0)
        + summary.get("total_disapproved", 0)
        + summary.get("total_pending", 0)
    )
    return {
        "active_students": summary.get("total_students", 0),
        "approved": summary.get("total_approved", 0),
        "disapproved": summary.get("total_disapproved", 0),
        "pending": summary.get("total_pending", 0),
        "cells": cells,
        "completion_percentage": summary.get("completion_percentage", 0.0),
    }
