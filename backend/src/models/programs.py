"""Programas de formación SENA reconocidos por su código en Zajuna.

El código sale del shortname del curso (``P_<código>_V_<ficha>_...``).
Un programa desconocido se muestra con el nombre completo del curso.
"""
from __future__ import annotations

PROGRAM_LABELS: dict[str, str] = {
    "228118": "ADSO",  # Tecnólogo en Análisis y Desarrollo de Software
    "233104": "TPS",  # Técnico en Programación de Software
}


def program_label(program_code: str, fullname: str = "") -> str:
    return PROGRAM_LABELS.get(program_code) or fullname or program_code
