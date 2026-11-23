"""Due process persistence: track stage progression per student per ficha."""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from src.config import DUE_PROCESS_DIR
from src.store.cached_json import invalidate, read_json_cached
from src.store.instructor_scope import scoped_dir

# Serializa TODAS las mutaciones del store (save/advance/delete): advance
# hace read-modify-write del archivo completo y dos requests concurrentes
# se pisarían el uno al otro sin esto. Las lecturas no lo necesitan
# (GIL + swap atómico del dict en el cache por mtime).
_write_lock = threading.Lock()

STAGES = [
    "sin_proceso",
    "primer_llamado",
    "segundo_llamado",
    "plan_mejoramiento",
    "comite",
]

STAGE_LABELS = {
    "sin_proceso": "Sin proceso",
    "primer_llamado": "Primer llamado de atención",
    "segundo_llamado": "Segundo llamado de atención",
    "plan_mejoramiento": "Plan de mejoramiento",
    "comite": "Comité de evaluación",
}


def _ficha_path(ficha: str) -> Path:
    """Return the JSON file path for a given ficha."""
    return scoped_dir(DUE_PROCESS_DIR) / f"{ficha}.json"


def get_next_stage(current_stage: str | None) -> str:
    """Determine the next stage in the due process sequence.

    None / 'sin_proceso' -> 'primer_llamado'
    'primer_llamado'     -> 'segundo_llamado'
    'segundo_llamado'    -> 'plan_mejoramiento'
    'plan_mejoramiento'  -> 'comite'
    'comite'             -> 'comite' (terminal)
    """
    if current_stage is None or current_stage == "sin_proceso":
        return "primer_llamado"
    try:
        idx = STAGES.index(current_stage)
    except ValueError:
        return "primer_llamado"
    if idx >= len(STAGES) - 1:
        return STAGES[-1]
    return STAGES[idx + 1]


def load_due_process(ficha: str) -> dict | None:
    """Load due process records for a ficha. Returns None if not found."""
    return read_json_cached(_ficha_path(ficha), default=None)


def _save_due_process_unlocked(ficha: str, data: dict) -> dict:
    """Persist due process data. Caller must hold ``_write_lock``."""
    scoped_dir(DUE_PROCESS_DIR).mkdir(parents=True, exist_ok=True)

    data["ficha"] = ficha
    data["updated_at"] = datetime.now().isoformat()

    path = _ficha_path(ficha)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    invalidate(path)
    return data


def save_due_process(ficha: str, data: dict) -> dict:
    """Save full due process data for a ficha. Returns stored data."""
    with _write_lock:
        return _save_due_process_unlocked(ficha, data)


def advance_due_process(
    ficha: str,
    user_id: int,
    full_name: str,
    document: str,
    evidence_ids: list[int],
    evidence_names: list[str],
) -> dict:
    """Advance a student to the next due process stage.

    Creates a new record if the student has no existing process.
    Appends a history entry and updates current_stage.
    Returns the updated record for this student.

    The whole read-modify-write cycle runs under ``_write_lock`` so that
    concurrent advances cannot overwrite each other.
    """
    with _write_lock:
        return _advance_due_process_unlocked(
            ficha, user_id, full_name, document, evidence_ids, evidence_names
        )


def _advance_due_process_unlocked(
    ficha: str,
    user_id: int,
    full_name: str,
    document: str,
    evidence_ids: list[int],
    evidence_names: list[str],
) -> dict:
    """Body of :func:`advance_due_process`. Caller must hold ``_write_lock``."""
    existing = load_due_process(ficha)
    if existing is None:
        existing = {"ficha": ficha, "records": {}}

    records = existing.get("records", {})
    uid_key = str(user_id)

    current_record = records.get(uid_key)
    if current_record is None:
        current_stage = "sin_proceso"
    else:
        current_stage = current_record.get("current_stage", "sin_proceso")

    next_stage = get_next_stage(current_stage)

    history_entry = {
        "stage": next_stage,
        "date": datetime.now().isoformat(),
        "evidence_ids": evidence_ids,
        "evidence_names": evidence_names,
        "email_generated": True,
    }

    if current_record is None:
        current_record = {
            "user_id": user_id,
            "full_name": full_name,
            "document": document,
            "current_stage": next_stage,
            "history": [history_entry],
        }
    else:
        current_record["current_stage"] = next_stage
        current_record["history"].append(history_entry)

    records[uid_key] = current_record
    existing["records"] = records
    _save_due_process_unlocked(ficha, existing)

    return current_record


def delete_due_process(ficha: str) -> bool:
    """Delete all due process records for a ficha."""
    with _write_lock:
        path = _ficha_path(ficha)
        if not path.exists():
            return False
        path.unlink()
        invalidate(path)
        return True
