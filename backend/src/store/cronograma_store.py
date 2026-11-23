"""Cronograma persistence: save/load/delete per-ficha cronogramas as JSON."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.config import CRONOGRAMAS_DIR
from src.store.instructor_scope import scoped_dir


def _ficha_path(ficha: str) -> Path:
    """Return the JSON file path for a given ficha."""
    return scoped_dir(CRONOGRAMAS_DIR) / f"{ficha}.json"


def resolve_evidence_id(evidence_name: str, snapshot: dict, ficha: str) -> int | None:
    """Try to match evidence_name to an item_id in the snapshot.

    Matches by checking if the evidence code appears in the evidence name
    from the grader data. For example, "GA1-220501092-AA1-EV01" would match
    an evidence named "GA1-220501092-AA1-EV01 Informe de análisis".
    """
    for course in snapshot.get("courses", []):
        if course.get("ficha") != ficha:
            continue
        for ev in course.get("evidences", []):
            ev_name = ev.get("name", "")
            # Exact match or code-prefix match
            if ev_name == evidence_name or evidence_name in ev_name or ev_name in evidence_name:
                return ev["item_id"]
    return None


def save_cronograma(ficha: str, entries: list[dict]) -> dict:
    """Save a cronograma for a ficha. Returns the stored data."""
    scoped_dir(CRONOGRAMAS_DIR).mkdir(parents=True, exist_ok=True)

    data = {
        "ficha": ficha,
        "updated_at": datetime.now().isoformat(),
        "entries": entries,
    }

    path = _ficha_path(ficha)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_cronograma(ficha: str) -> dict | None:
    """Load a cronograma for a ficha. Returns None if not found."""
    path = _ficha_path(ficha)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw)


def delete_cronograma(ficha: str) -> bool:
    """Delete a cronograma for a ficha. Returns True if deleted, False if not found."""
    path = _ficha_path(ficha)
    if not path.exists():
        return False
    path.unlink()
    return True
