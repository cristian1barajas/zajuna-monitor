"""Executor dedicado para operaciones lentas contra Zajuna.

Los endpoints que hablan con Zajuna en vivo (validar credenciales,
verificar entregas) tardan de 10 a 60+ segundos por los delays humanos y
los reintentos. Si corren como rutas `def` normales, ocupan slots del
threadpool compartido de anyio (~40) y pueden dejar sin hilos a los
endpoints rápidos del dashboard cuando varios instructores los disparan
a la vez.

Este pool separado y acotado los aísla: los endpoints se declaran
`async def` y delegan el trabajo bloqueante aquí con `run_in_zajuna_pool`.
El límite bajo además evita bombardear a Zajuna con demasiadas sesiones
simultáneas.
"""
from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")

# Acotado a propósito: Zajuna no aguanta muchas sesiones simultáneas
ZAJUNA_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="zajuna-slow")


async def run_in_zajuna_pool(fn: Callable[[], T]) -> T:
    """Ejecuta una función bloqueante en el pool dedicado sin ocupar
    el threadpool general de la API."""
    loop = asyncio.get_running_loop()
    # run_in_executor no copia el contexto: sin esto el hilo pierde al
    # instructor de la petición y los stores escribirían en la carpeta común.
    ctx = contextvars.copy_context()
    return await loop.run_in_executor(ZAJUNA_POOL, ctx.run, fn)
