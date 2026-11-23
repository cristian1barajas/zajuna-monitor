"""Endurecimiento de la API: configuración de seguridad, cabeceras, límites
de tamaño y de frecuencia, y el guard de acceso por ficha.

La configuración sale del entorno o de ``backend/.env`` (las variables del
entorno ganan). Sin ``CMM_JWT_SECRET_KEY`` fuerte la API no arranca: con un
secreto conocido cualquiera puede firmar un token de instructor.
"""
from __future__ import annotations

import inspect
import re
import threading
import time
from collections import deque
from functools import lru_cache

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config import BASE_DIR

# Valores que ya circularon en el código o en ejemplos: nunca sirven de secreto.
_KNOWN_WEAK_SECRETS = {
    "tu_secreto_que_sea_dificil",
    "replace-with-the-same-secret-as-cmm-backend",
    "secret",
    "changeme",
}
MIN_SECRET_BYTES = 32  # HS256 pide una llave de al menos 256 bits

FICHA_RE = re.compile(r"^\d{1,15}$")


class SecuritySettings(BaseSettings):
    """Ajustes de seguridad (entorno o backend/.env)."""

    cmm_jwt_secret_key: str
    cmm_jwt_algorithm: str = "HS256"
    # development | production
    app_env: str = "development"
    # Orígenes permitidos por CORS, separados por coma.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Tamaño máximo del cuerpo de una petición (MB).
    max_body_mb: int = 30
    # Peticiones por minuto a /api por usuario (o por IP sin token). 0 = sin límite.
    rate_limit_per_minute: int = 600
    # Herramientas que actúan sobre la máquina del servidor como si fuera el PC
    # del instructor (Soportes de Outlook abre un Chrome; la importación de
    # teléfonos lee una carpeta local). En producción quedan apagadas salvo
    # que se activen.
    local_tools_enabled: bool | None = None

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cmm_jwt_secret_key")
    @classmethod
    def _strong_secret(cls, value: str) -> str:
        value = value.strip()
        if value in _KNOWN_WEAK_SECRETS or len(value.encode("utf-8")) < MIN_SECRET_BYTES:
            raise ValueError(
                f"CMM_JWT_SECRET_KEY debe tener al menos {MIN_SECRET_BYTES} bytes aleatorios "
                "y ser el mismo JWT_SECRET_KEY del backend CMM (ver scripts/generar_secreto_jwt.ps1)"
            )
        return value

    @field_validator("cmm_jwt_algorithm")
    @classmethod
    def _hmac_algorithm(cls, value: str) -> str:
        if value not in {"HS256", "HS384", "HS512"}:
            raise ValueError("CMM_JWT_ALGORITHM debe ser HS256, HS384 o HS512")
        return value

    @field_validator("app_env")
    @classmethod
    def _known_env(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"development", "production"}:
            raise ValueError("APP_ENV debe ser development o production")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def local_tools(self) -> bool:
        if self.local_tools_enabled is None:
            return not self.is_production
        return self.local_tools_enabled


@lru_cache
def get_security_settings() -> SecuritySettings:
    return SecuritySettings()  # type: ignore[call-arg]


# --- Cabeceras de seguridad ---

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    # Solo el mismo sitio puede incrustar respuestas de la API (fetch con CORS no se afecta).
    "Cross-Origin-Resource-Policy": "same-site",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    is_docs = path in {"/docs", "/redoc"}
    for name, value in _BASE_HEADERS.items():
        # Swagger UI carga scripts y estilos de un CDN: no se le pone la CSP de la API.
        if is_docs and name == "Content-Security-Policy":
            continue
        response.headers.setdefault(name, value)
    if path.startswith("/api/"):
        # Datos personales de aprendices: que ningún proxy ni navegador los guarde.
        response.headers.setdefault("Cache-Control", "no-store")
    if get_security_settings().is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


# --- Límite de tamaño del cuerpo ---

async def body_size_limit_middleware(request: Request, call_next):
    limit = get_security_settings().max_body_mb * 1024 * 1024
    length = request.headers.get("content-length")
    if length is not None:
        try:
            too_big = int(length) > limit
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Content-Length inválido"})
        if too_big:
            return JSONResponse(status_code=413, content={"detail": "El archivo o la petición es demasiado grande"})
    elif request.method in {"POST", "PUT", "PATCH"} and request.headers.get("transfer-encoding"):
        # Sin Content-Length no se puede medir antes de leer: se rechaza el chunked.
        return JSONResponse(status_code=411, content={"detail": "Falta Content-Length"})
    return await call_next(request)


# --- Límite de frecuencia (ventana deslizante de 60 s, en memoria por proceso) ---

_hits: dict[str, deque[float]] = {}
_hits_lock = threading.Lock()


def _client_key(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user and user.get("id") is not None:
        return f"u:{user['id']}"
    return f"ip:{request.client.host if request.client else 'desconocido'}"


def _over_limit(key: str, limit: int, now: float) -> bool:
    with _hits_lock:
        window = _hits.setdefault(key, deque())
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            return True
        window.append(now)
        if len(_hits) > 10_000:  # no dejar crecer el diccionario sin fin
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
                del _hits[k]
        return False


async def rate_limit_middleware(request: Request, call_next):
    limit = get_security_settings().rate_limit_per_minute
    if (
        limit > 0
        and request.url.path.startswith("/api/")
        and request.method != "OPTIONS"
        and _over_limit(_client_key(request), limit, time.monotonic())
    ):
        return JSONResponse(
            status_code=429,
            content={"detail": "Demasiadas peticiones. Intenta de nuevo en un minuto."},
            headers={"Retry-After": "60"},
        )
    return await call_next(request)


def reset_rate_limits() -> None:
    """Para tests."""
    with _hits_lock:
        _hits.clear()


# --- Guard por ficha ---

def require_ficha_access(request: Request) -> None:
    """Toda ruta con ``{ficha}`` exige una ficha válida que el instructor siga.

    El número de ficha arma rutas de archivo (``data/<store>/<ficha>.json``):
    solo dígitos, nada de ``..`` ni separadores. Y como los stores por ficha
    todavía no están particionados por instructor, nadie puede leer ni
    escribir los de un grupo que no está en SU snapshot.
    """
    ficha = request.path_params.get("ficha")
    if ficha is None:
        return
    if not FICHA_RE.fullmatch(ficha):
        raise HTTPException(status_code=400, detail="Número de ficha inválido")
    # Se resuelve aquí (y no con Depends) para que solo cueste en rutas con ficha;
    # se respeta dependency_overrides de get_snapshot (tests).
    from src.api.dependencies import get_snapshot  # import tardío: evita el ciclo

    override = request.app.dependency_overrides.get(get_snapshot)
    if override is None:
        snapshot = get_snapshot(request)
    else:
        snapshot = override(request) if inspect.signature(override).parameters else override()
    if not any(c.get("ficha") == ficha for c in snapshot.get("courses", [])):
        raise HTTPException(status_code=404, detail=f"Ficha {ficha} no encontrada")

