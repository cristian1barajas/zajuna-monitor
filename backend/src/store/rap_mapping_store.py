"""RAP mapping persistence: save/load/delete per-ficha evidence→RAP mappings as JSON."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.config import RAP_MAPPINGS_DIR
from src.store.cached_json import invalidate, read_json_cached
from src.store.instructor_scope import scoped_dir


def _ficha_path(ficha: str) -> Path:
    """Return the JSON file path for a given ficha."""
    return scoped_dir(RAP_MAPPINGS_DIR) / f"{ficha}.json"


def save_rap_mapping(ficha: str, data: dict) -> dict:
    """Save a RAP mapping for a ficha. Returns the stored data."""
    scoped_dir(RAP_MAPPINGS_DIR).mkdir(parents=True, exist_ok=True)

    data["ficha"] = ficha
    data["updated_at"] = datetime.now().isoformat()

    path = _ficha_path(ficha)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    invalidate(path)
    return data


def load_rap_mapping(ficha: str) -> dict | None:
    """Load a RAP mapping for a ficha. Returns None if not found."""
    return read_json_cached(_ficha_path(ficha), default=None)


def delete_rap_mapping(ficha: str) -> bool:
    """Delete a RAP mapping for a ficha. Returns True if deleted, False if not found."""
    path = _ficha_path(ficha)
    if not path.exists():
        return False
    path.unlink()
    invalidate(path)
    return True
