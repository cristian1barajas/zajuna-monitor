"""Registro de cursos Zajuna que cada instructor decidió monitorear.

Es la fuente de verdad de "qué fichas sigue el instructor": el scraper
toma de aquí los course_ids a refrescar y la API resuelve ficha → course_id
sin depender de que la ficha ya esté en el snapshot. Así una ficha recién
agregada (p. ej. un grupo nuevo) se puede sincronizar sola desde el primer día.

Archivo: data/instructors/<cmm_user_id>/courses.json
    {"updated_at": "...",
     "courses": [{"course_id", "ficha", "shortname", "fullname",
                  "program_code", "added_at"}]}

Mientras un instructor no tenga registro (archivo ausente), las funciones
de lectura devuelven None y los llamadores conservan el comportamiento
legado (snapshot / ZAJUNA_COURSE_IDS del .env).
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from src.config import instructor_data_dir

logger = logging.getLogger(__name__)

FILENAME = "courses.json"


def _path(user_id: str) -> Path:
    return instructor_data_dir(user_id) / FILENAME


def load_tracked(user_id: str | None) -> list[dict] | None:
    """Cursos seguidos por el instructor, o None si aún no tiene registro."""
    if user_id is None:
        return None
    path = _path(user_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("No se pudo leer %s: %s", path, exc)
        return None
    return data.get("courses", [])


def save_tracked(user_id: str, courses: list[dict]) -> list[dict]:
    """Reemplaza la selección del instructor, conservando ``added_at`` previos."""
    previous = {c["course_id"]: c for c in load_tracked(user_id) or []}
    now = datetime.now(UTC).isoformat()
    records = [
        {
            "course_id": c["course_id"],
            "ficha": c["ficha"],
            "shortname": c.get("shortname", ""),
            "fullname": c.get("fullname", ""),
            "program_code": c.get("program_code", ""),
            "added_at": previous.get(c["course_id"], {}).get("added_at", now),
        }
        for c in courses
    ]
    path = _path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({"updated_at": now, "courses": records}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(path)
    logger.info(
        "Cursos seguidos actualizados para usuario CMM %s: fichas %s",
        user_id, [r["ficha"] for r in records],
    )
    return records


def tracked_course_ids(user_id: str | None) -> list[int] | None:
    tracked = load_tracked(user_id)
    if tracked is None:
        return None
    return [c["course_id"] for c in tracked]


def ficha_for_course(user_id: str | None, course_id: int) -> str | None:
    for course in load_tracked(user_id) or []:
        if course["course_id"] == course_id:
            return course["ficha"] or None
    return None


def course_ids_for_fichas(user_id: str | None, fichas: list[str]) -> dict[str, int]:
    """Mapa ficha → course_id para las fichas pedidas que estén en el registro."""
    wanted = set(fichas)
    return {
        c["ficha"]: c["course_id"]
        for c in load_tracked(user_id) or []
        if c["ficha"] in wanted
    }
