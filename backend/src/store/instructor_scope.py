"""Instructor dueño de los datos que se leen y escriben en esta petición.

Los stores por ficha (sofia_reports, cronogramas, debido proceso…) guardan
en ``<carpeta del store>/<id del instructor>/<ficha>.json``: dos instructores
con el mismo grupo no se pisan. El middleware de autenticación fija el
instructor para toda la petición; los hilos en segundo plano lo heredan si se
lanzan con ``contextvars.copy_context().run`` (ver ``start_thread``).

Sin instructor (scripts por consola, tests de stores) se usa la carpeta
del store tal cual, como antes de particionar.
"""
from __future__ import annotations

import contextvars
import re
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

current_instructor: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_instructor", default=None
)


def validate_user_id(user_id: str | int) -> str:
    """El id del CMM arma rutas de archivo: nada de separadores ni ``..``."""
    value = str(user_id)
    if not _USER_ID_RE.fullmatch(value):
        raise ValueError(f"Id de instructor inválido: {value!r}")
    return value


@contextmanager
def as_instructor(user_id: str | int | None) -> Iterator[None]:
    """Fija el instructor mientras dura el bloque."""
    token = current_instructor.set(None if user_id is None else validate_user_id(user_id))
    try:
        yield
    finally:
        current_instructor.reset(token)


def scoped_dir(base: Path) -> Path:
    """Carpeta del store para el instructor actual (o la base sin instructor)."""
    user_id = current_instructor.get()
    return base / user_id if user_id is not None else base


def start_thread(target: Callable[..., object], *args: object) -> threading.Thread:
    """Hilo daemon que conserva el instructor (y el resto del contexto) actual."""
    ctx = contextvars.copy_context()
    thread = threading.Thread(target=ctx.run, args=(target, *args), daemon=True)
    thread.start()
    return thread
