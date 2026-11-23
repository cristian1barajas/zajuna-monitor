"""Cache de respuestas serializadas para los endpoints de lectura.

Los endpoints de dashboard/fichas/alerts/activity son funciones puras del
snapshot (data/latest.json), que solo cambia cuando corre el scraper. Sin
este cache, cada request recomputaba las estadísticas (decenas de miles de
iteraciones) y re-serializaba ~537 KB de JSON — trabajo CPU bajo el GIL que
saturaba el proceso con pocos usuarios concurrentes.

Estrategia: la PRIMERA petición a una ruta calcula la respuesta y se
guardan los bytes finales (crudos y gzip) keyed por (ruta+query, mtime del
snapshot). Las siguientes se sirven directo de memoria (~0 CPU) hasta que
el snapshot cambie de mtime. El gzip se comprime UNA vez por cambio de
snapshot, no por request.

Se desactiva con ZAJUNA_RESPONSE_CACHE=0 (los tests lo apagan porque
mockean el snapshot por dependency_overrides y el archivo real no cambia).
"""
from __future__ import annotations

import gzip
import logging
import os
import re
import threading

from fastapi import Request, Response

logger = logging.getLogger(__name__)


# Rutas cacheables: dependen SOLO del snapshot (no de cronogramas,
# novedades, mapeos RAP ni otros stores que cambian por fuera del scrape).
CACHEABLE_PATTERNS = [
    re.compile(r"^/api/dashboard$"),
    re.compile(r"^/api/fichas$"),
    re.compile(r"^/api/fichas/[^/]+$"),
    re.compile(r"^/api/fichas/[^/]+/pendientes$"),
    re.compile(r"^/api/alerts$"),
    re.compile(r"^/api/activity(/[^/]+)?$"),
]

MAX_ENTRIES = 256
GZIP_MIN_SIZE = 1024

# key -> (mtime, raw_bytes, gzip_bytes | None)
_cache: dict[str, tuple[tuple[float, float], bytes, bytes | None]] = {}
_lock = threading.Lock()


def cache_enabled() -> bool:
    return os.environ.get("ZAJUNA_RESPONSE_CACHE", "1") != "0"


def clear() -> None:
    """Vacía el cache (usado por tests)."""
    with _lock:
        _cache.clear()


def _snapshot_mtime(request: Request) -> tuple[float, float] | None:
    """Versión de lo que ve el usuario: mtime de SU snapshot y de su registro
    de grupos seguidos.

    Crítico en multi-instructor: la validez del cache depende del snapshot
    que ese usuario ve, no del global. El registro también cuenta porque
    quitar o agregar un grupo cambia lo visible sin tocar el snapshot.
    """
    # Import tardío para evitar ciclo dependencies <-> response_cache
    from src.api.dependencies import snapshot_path_for
    from src.config import instructor_data_dir
    from src.store.tracked_courses_store import FILENAME

    try:
        snapshot = snapshot_path_for(request).stat().st_mtime
    except OSError:
        return None
    user = getattr(request.state, "user", None)
    tracked = 0.0
    if user and user.get("id") is not None:
        try:
            tracked = (instructor_data_dir(user["id"]) / FILENAME).stat().st_mtime
        except OSError:
            tracked = 0.0
    return snapshot, tracked


def _is_cacheable(path: str) -> bool:
    return any(p.match(path) for p in CACHEABLE_PATTERNS)


def _accepts_gzip(request: Request) -> bool:
    return "gzip" in request.headers.get("Accept-Encoding", "").lower()


def _build_response(
    raw: bytes, gz: bytes | None, request: Request, cache_state: str
) -> Response:
    headers = {"X-Cache": cache_state, "Vary": "Accept-Encoding"}
    if gz is not None and _accepts_gzip(request):
        headers["Content-Encoding"] = "gzip"
        return Response(content=gz, media_type="application/json", headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


async def response_cache_middleware(request: Request, call_next):
    """Sirve GETs de lectura desde memoria mientras el snapshot no cambie."""
    if (
        request.method != "GET"
        or not cache_enabled()
        or not _is_cacheable(request.url.path)
    ):
        return await call_next(request)

    mtime = _snapshot_mtime(request)
    if mtime is None:
        return await call_next(request)

    # La key incluye al usuario: cada instructor ve SU snapshot — jamás
    # servir el cache de otro.
    user = getattr(request.state, "user", None)
    user_id = user.get("id") if user else "anon"
    key = (
        f"{user_id}:{request.url.path}"
        + (f"?{request.url.query}" if request.url.query else "")
    )

    with _lock:
        entry = _cache.get(key)
    if entry is not None and entry[0] == mtime:
        return _build_response(entry[1], entry[2], request, "HIT")

    response = await call_next(request)
    if response.status_code != 200:
        return response

    # Materializar el cuerpo del streaming response
    body = b"".join([chunk async for chunk in response.body_iterator])

    gz = gzip.compress(body, compresslevel=6) if len(body) >= GZIP_MIN_SIZE else None

    with _lock:
        if len(_cache) >= MAX_ENTRIES:
            _cache.clear()
        _cache[key] = (mtime, body, gz)

    return _build_response(body, gz, request, "MISS")
