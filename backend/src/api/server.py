"""FastAPI application for the Zajuna Monitor API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from src.api.auth import cmm_auth_middleware
from src.api.dependencies import get_base_config, load_snapshot
from src.api.response_cache import response_cache_middleware
from src.api.routes import (
    actas_equipo_ejecutor,
    activity,
    complaint_reports,
    courses,
    cronograma,
    dashboard,
    download_evidences,
    due_process,
    fichas,
    forums,
    juicios,
    novedades,
    outlook_soportes,
    pending_grading,
    reports,
    scraper,
    zajuna_account,
)
from src.api.security import (
    body_size_limit_middleware,
    get_security_settings,
    rate_limit_middleware,
    require_ficha_access,
    security_headers_middleware,
)

logger = logging.getLogger(__name__)
security = get_security_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load snapshot into memory on startup."""
    logger.info("Loading initial snapshot...")
    try:
        snapshot = load_snapshot()
        logger.info(
            "API ready. %d courses loaded.",
            len(snapshot.get("courses", [])),
        )
    except Exception as e:
        logger.warning("No snapshot available at startup: %s", e)
    yield


app = FastAPI(
    title="Zajuna Monitor API",
    version="1.0.0",
    description="API REST for Zajuna (SENA Moodle) grading data",
    lifespan=lifespan,
    # En producción no se publica el mapa de la API.
    docs_url=None if security.is_production else "/docs",
    redoc_url=None if security.is_production else "/redoc",
    openapi_url=None if security.is_production else "/openapi.json",
    # Toda ruta con {ficha} valida el número y que el grupo sea del instructor.
    dependencies=[Depends(require_ficha_access)],
    # orjson serializa varias veces más rápido que el json de la stdlib —
    # importa en los cache-miss y en los endpoints no cacheables.
    default_response_class=ORJSONResponse,
)

# Orden de middlewares (el último agregado queda por FUERA):
#   CORS -> cabeceras -> tamaño -> auth -> frecuencia -> response_cache -> rutas
# El cache va lo más adentro posible: solo responde tras pasar el auth.
# La frecuencia va después del auth para contar por usuario y no por IP.
app.middleware("http")(response_cache_middleware)
app.middleware("http")(rate_limit_middleware)

# Auth: valida el JWT del Sistema CMM en todo /api/* (excepto /api/health).
app.middleware("http")(cmm_auth_middleware)
app.middleware("http")(body_size_limit_middleware)
app.middleware("http")(security_headers_middleware)

# CORS: orígenes desde CORS_ORIGINS (en producción, solo el dominio del frontend).
app.add_middleware(
    CORSMiddleware,
    allow_origins=security.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    # El front lee el nombre del archivo de las descargas (.eml/.zip).
    expose_headers=["Content-Disposition"],
)

# Routers
app.include_router(dashboard.router)
app.include_router(fichas.router)
app.include_router(activity.router)
app.include_router(cronograma.router)
app.include_router(reports.router)
app.include_router(scraper.router)
app.include_router(due_process.router)
app.include_router(juicios.router)
app.include_router(pending_grading.router)
app.include_router(forums.router)
app.include_router(complaint_reports.router)
app.include_router(download_evidences.router)
app.include_router(novedades.router)
if security.local_tools:
    # Abre un Chrome en la máquina del servidor: solo para uso local.
    app.include_router(outlook_soportes.router)
app.include_router(actas_equipo_ejecutor.router)
app.include_router(zajuna_account.router)
app.include_router(courses.router)


if __name__ == "__main__":
    import uvicorn

    config = get_base_config()
    uvicorn.run(
        "src.api.server:app",
        host=config.api_host,
        port=config.api_port,
        reload=True,
    )
