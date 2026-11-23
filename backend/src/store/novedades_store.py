"""Novedades persistence: track students with administrative novelties per ficha.

A 'novedad' marks a student who has a pending administrative process
(e.g. cancellation in progress) so they can be excluded from due process
emails, heatmap PDFs, and reports.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from src.config import NOVEDADES_DIR
from src.store.cached_json import invalidate, read_json_cached
from src.store.instructor_scope import scoped_dir

# Serializa las mutaciones del store: save/remove hacen read-modify-write
# del archivo completo y dos requests concurrentes se pisarían sin esto.
# Las lecturas no lo necesitan (GIL + swap atómico del cache por mtime).
_write_lock = threading.Lock()

NOVEDAD_TYPES = {
    "cancelacion": "Cancelacion en proceso",
    "retiro_voluntario": "Retiro voluntario",
    "traslado": "Traslado de ficha",
    "otro": "Otro",
}


def _ficha_path(ficha: str) -> Path:
    """Return the JSON file path for a given ficha."""
    return scoped_dir(NOVEDADES_DIR) / f"{ficha}.json"


def load_novedades(ficha: str) -> dict | None:
    """Load all novedades for a ficha. Returns None if no file exists."""
    return read_json_cached(_ficha_path(ficha), default=None)


def load_novedades_set(ficha: str) -> set[int]:
    """Load just the set of user_ids that have novedades. Lightweight helper."""
    data = load_novedades(ficha)
    if not data:
        return set()
    return {int(uid) for uid in data.get("records", {})}


def save_novedades(ficha: str, user_ids: list[int], type_: str, note: str,
                   snapshot: dict | None = None) -> dict:
    """Add novedades for multiple students in a ficha.

    If a student already has a novedad, it will be updated.
    Returns the full novedades data.
    """
    with _write_lock:
        scoped_dir(NOVEDADES_DIR).mkdir(parents=True, exist_ok=True)
        data = load_novedades(ficha) or {
            "ficha": ficha,
            "updated_at": None,
            "records": {},
        }

        # Build student info lookup from snapshot if available
        student_info: dict[int, dict] = {}
        if snapshot:
            for course in snapshot.get("courses", []):
                if course.get("ficha") == ficha:
                    for s in course.get("students", []):
                        student_info[s["user_id"]] = s
                    break

        now = datetime.now().isoformat()

        for uid in user_ids:
            info = student_info.get(uid, {})
            data["records"][str(uid)] = {
                "user_id": uid,
                "full_name": info.get("full_name", ""),
                "document": info.get("document", ""),
                "type": type_,
                "type_label": NOVEDAD_TYPES.get(type_, type_),
                "note": note,
                "created_at": data["records"].get(str(uid), {}).get("created_at", now),
                "updated_at": now,
            }

        data["updated_at"] = now
        path = _ficha_path(ficha)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        invalidate(path)
        return data


def remove_novedades(ficha: str, user_ids: list[int]) -> dict:
    """Remove novedades for specific students. Returns updated data."""
    with _write_lock:
        scoped_dir(NOVEDADES_DIR).mkdir(parents=True, exist_ok=True)
        data = load_novedades(ficha) or {
            "ficha": ficha,
            "updated_at": None,
            "records": {},
        }

        for uid in user_ids:
            data["records"].pop(str(uid), None)

        data["updated_at"] = datetime.now().isoformat()

        path = _ficha_path(ficha)
        if data["records"]:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            # Clean up empty file
            if path.exists():
                path.unlink()
        invalidate(path)

        return data


def delete_all_novedades(ficha: str) -> bool:
    """Delete all novedades for a ficha. Returns True if file existed."""
    with _write_lock:
        path = _ficha_path(ficha)
        if path.exists():
            path.unlink()
            invalidate(path)
            return True
        return False
