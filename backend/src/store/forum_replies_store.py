"""Última revisión de réplicas por foro, por ficha y por instructor.

``data/forum_replies/<instructor>/<ficha>.json``::

    {"ficha": "3389000", "forums": {"565592": {
        "forum_id": 565592, "item_id": 2503062, "name": "...",
        "checked_at": "...", "total_discussions": 22, "peer_replies": 9,
        "failed_discussions": [], "contributions": [...]}}}

Los aportes se guardan sin estado: el estado (vencido, a tiempo…) depende
del día y se calcula al leer (``src.api.forum_inbox``). Guarda un extracto
del texto del aprendiz, igual que el snapshot guarda nombres y notas: es
dato local del instructor y nunca se manda a terceros.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from src.config import FORUM_REPLIES_DIR
from src.store.cached_json import invalidate, read_json_cached
from src.store.instructor_scope import scoped_dir

_write_lock = threading.Lock()


def _ficha_path(ficha: str) -> Path:
    return scoped_dir(FORUM_REPLIES_DIR) / f"{ficha}.json"


def load_forum_replies(ficha: str) -> dict | None:
    return read_json_cached(_ficha_path(ficha), default=None)


def load_forum(ficha: str, forum_id: int) -> dict | None:
    data = load_forum_replies(ficha)
    return (data or {}).get("forums", {}).get(str(forum_id))


def save_forum(ficha: str, forum: dict) -> None:
    """Reemplaza la revisión guardada de un foro (los demás foros se conservan)."""
    with _write_lock:
        path = _ficha_path(ficha)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Copia: el dict del cache lo comparten las lecturas en curso
        current = load_forum_replies(ficha) or {}
        data = {"ficha": ficha, "forums": {**current.get("forums", {}), str(forum["forum_id"]): forum}}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        invalidate(path)
