"""Registro de soportes de llamados y datos de las actas del equipo ejecutor, por ficha.

- ``soportes_llamados/<ficha>.json``: cada correo impreso desde Outlook y en
  qué ZIP quedó (uno por id de correo; una nueva descarga lo actualiza).
- ``actas_equipo_ejecutor/<ficha>.json``: asistentes, horas y último número
  de acta usados, para proponerlos en la siguiente acta.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from src.config import ACTAS_DIR, SOPORTES_DIR
from src.store.cached_json import invalidate, read_json_cached
from src.store.instructor_scope import scoped_dir

_write_lock = threading.Lock()


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    invalidate(path)


# --- Soportes descargados ---


def _soportes_path(ficha: str) -> Path:
    return scoped_dir(SOPORTES_DIR) / f"{ficha}.json"


def load_soportes(ficha: str) -> list[dict]:
    data = read_json_cached(_soportes_path(ficha), default=None) or {}
    return list(data.get("records", {}).values())


def record_soportes(ficha: str, entries: list[dict], zip_name: str) -> None:
    """Guarda los correos impresos en una descarga.

    Cada entrada: ``message_id``, ``stage``, ``student_name``, ``subject``,
    ``sent_at`` (ISO, hora de Colombia), ``to`` y ``archivo`` (ruta en el ZIP).
    """
    now = datetime.now().isoformat(timespec="seconds")
    with _write_lock:
        path = _soportes_path(ficha)
        data = read_json_cached(path, default=None) or {"ficha": ficha, "records": {}}
        for e in entries:
            data["records"][e["message_id"]] = {**e, "zip": zip_name, "descargado_at": now}
        data["updated_at"] = now
        _write(path, data)


# --- Actas del equipo ejecutor ---

DEFAULT_ACTA = {
    "asistentes": [],
    "ultimo_numero": 0,
    "hora_inicio": "08:00 p.m.",
    "hora_fin": "09:00 p.m.",
}


def _actas_path(ficha: str) -> Path:
    return scoped_dir(ACTAS_DIR) / f"{ficha}.json"


def load_acta_config(ficha: str) -> dict:
    return {**DEFAULT_ACTA, **(read_json_cached(_actas_path(ficha), default=None) or {})}


def save_acta_config(ficha: str, *, numero: int, asistentes: list[dict], hora_inicio: str, hora_fin: str, fecha_envio: str) -> None:
    with _write_lock:
        data = load_acta_config(ficha)
        data.update(
            asistentes=asistentes,
            ultimo_numero=max(int(data.get("ultimo_numero") or 0), numero),
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
        )
        generadas = [g for g in data.get("generadas", []) if g.get("fecha_envio") != fecha_envio]
        generadas.append(
            {"fecha_envio": fecha_envio, "numero": numero, "generada_at": datetime.now().isoformat(timespec="seconds")}
        )
        data["generadas"] = sorted(generadas, key=lambda g: g["fecha_envio"])
        _write(_actas_path(ficha), data)
