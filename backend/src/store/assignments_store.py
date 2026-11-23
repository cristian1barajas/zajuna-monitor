"""Assignments persistence: save/load/delete per-ficha assignment mappings as JSON.

Stores the item_id <-> cmid mapping for each ficha, built during sync
from the assignments index page.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.config import ASSIGNMENTS_DIR
from src.store.cached_json import invalidate, read_json_cached
from src.store.instructor_scope import scoped_dir


def _ficha_path(ficha: str) -> Path:
    """Return the JSON file path for a given ficha."""
    return scoped_dir(ASSIGNMENTS_DIR) / f"{ficha}.json"


def save_assignments(ficha: str, course_id: int, assignments: list[dict]) -> dict:
    """Save assignment mappings for a ficha. Returns the stored data.

    Args:
        ficha: The ficha identifier (e.g., "3388997").
        course_id: The Moodle course ID.
        assignments: List of dicts with name, cmid, and optionally item_id.
    """
    scoped_dir(ASSIGNMENTS_DIR).mkdir(parents=True, exist_ok=True)

    data = {
        "ficha": ficha,
        "course_id": course_id,
        "updated_at": datetime.now().isoformat(),
        "assignments": assignments,
    }

    path = _ficha_path(ficha)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    invalidate(path)
    return data


def load_assignments(ficha: str) -> dict | None:
    """Load assignment mappings for a ficha. Returns None if not found."""
    return read_json_cached(_ficha_path(ficha), default=None)


def delete_assignments(ficha: str) -> bool:
    """Delete assignment mappings for a ficha. Returns True if deleted."""
    path = _ficha_path(ficha)
    if not path.exists():
        return False
    path.unlink()
    invalidate(path)
    return True
