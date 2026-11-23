"""Lector JSON cacheado por mtime para los stores basados en archivos.

Los stores releían el disco (read_text + json.loads) en CADA request. Este
módulo cachea el resultado parseado por (path, mtime) con un dict a nivel de
módulo protegido por threading.Lock — mismo patrón que
src/store/zajuna_accounts_store.py::_load, generalizado para cualquier store.

Contrato:
- Archivo inexistente -> se retorna ``default`` (sin cachear).
- Errores de parseo (JSONDecodeError) u OSError de lectura se PROPAGAN,
  igual que en los loaders originales; cada caller decide si los captura.
- Las escrituras deben llamar ``invalidate(path)`` tras persistir para no
  depender de la resolución del mtime del filesystem (igual que hace
  zajuna_accounts_store._save).

Nota: el valor cacheado es un objeto compartido entre requests. Los callers
de lectura no deben mutarlo; las funciones de mutación de los stores lo
mutan solo dentro de su ciclo load -> modify -> save + invalidate (bajo el
lock de escritura del store), tras lo cual la entrada se descarta.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

# key: str(path) -> (mtime, datos parseados)
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def read_json_cached(path: Path, default: Any = None) -> Any:
    """Lee y parsea ``path`` como JSON, cacheando por mtime.

    Retorna ``default`` si el archivo no existe. Propaga JSONDecodeError /
    OSError de lectura (mismo comportamiento que los loaders sin cache).
    """
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return default

    key = str(path)
    with _cache_lock:
        entry = _cache.get(key)
        if entry is not None and entry[0] == mtime:
            return entry[1]

    # Parsear fuera del lock: la carrera benigna (doble parseo) es preferible
    # a serializar todas las lecturas detrás de un json.loads potencialmente
    # grande.
    data = json.loads(path.read_text(encoding="utf-8"))

    with _cache_lock:
        _cache[key] = (mtime, data)
    return data


def invalidate(path: Path) -> None:
    """Descarta la entrada de cache de ``path`` (llamar tras escribir/borrar)."""
    with _cache_lock:
        _cache.pop(str(path), None)
