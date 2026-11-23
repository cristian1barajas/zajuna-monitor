"""JWT validation against the shared CMM auth (Sistema CMM API).

The monitor does not issue tokens: it trusts the access tokens signed by
the CMM backend (HS256, shared secret CMM_JWT_SECRET_KEY from the
environment or backend/.env; without a strong one the API does not start).
Every /api/* request must carry `Authorization: Bearer <token>` except
the public health check.

Token payload (as issued by the CMM backend):
    {"sub": "<user_id>", "role": "instructor", "exp": ..., "type": "access"}
"""
from __future__ import annotations

import logging

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

from src.api.security import get_security_settings
from src.store.instructor_scope import as_instructor, validate_user_id

logger = logging.getLogger(__name__)

_settings = get_security_settings()
CMM_JWT_SECRET_KEY = _settings.cmm_jwt_secret_key
CMM_JWT_ALGORITHM = _settings.cmm_jwt_algorithm

# Roles del CMM con acceso al monitor
MONITOR_ROLES = {"instructor", "admin"}

# Rutas públicas (sin token). La documentación de la API solo existe en desarrollo.
PUBLIC_PATHS = {"/api/health", "/docs", "/openapi.json", "/redoc"}


def decode_cmm_token(token: str) -> dict:
    """Decode and validate a CMM access token. Raises jwt exceptions on failure."""
    payload = jwt.decode(
        token,
        CMM_JWT_SECRET_KEY,
        algorithms=[CMM_JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    try:
        # El id arma rutas de archivo (data/<store>/<id>/…): solo caracteres seguros.
        payload["sub"] = validate_user_id(str(payload.get("sub", "")).strip())
    except ValueError as exc:
        raise jwt.InvalidTokenError("Token sin usuario válido") from exc
    return payload


def _identify_optional(request: Request) -> None:
    """Set request.state.user from a valid token; ignore missing or bad ones."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return
    try:
        payload = decode_cmm_token(auth_header.removeprefix("Bearer ").strip())
    except jwt.InvalidTokenError:
        return
    role = payload.get("role", "")
    if role in MONITOR_ROLES:
        request.state.user = {"id": payload.get("sub"), "role": role}


async def cmm_auth_middleware(request: Request, call_next):
    """Enforce CMM JWT auth on /api/* (except PUBLIC_PATHS and CORS preflights)."""
    path = request.url.path

    if request.method == "OPTIONS" or not path.startswith("/api/"):
        return await call_next(request)

    if path in PUBLIC_PATHS:
        # Pública, pero si trae un token válido se identifica al instructor:
        # /api/health debe reportar la sincronización de SU snapshot, no la global.
        _identify_optional(request)
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "No autenticado"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_cmm_token(auth_header.removeprefix("Bearer ").strip())
    except jwt.ExpiredSignatureError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Token expirado"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT del CMM rechazado (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=401,
            content={"detail": "Token inválido"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = payload.get("role", "")
    if role not in MONITOR_ROLES:
        return JSONResponse(
            status_code=403,
            content={"detail": f"El rol '{role}' no tiene acceso al monitor"},
        )

    # Disponible para las rutas, y los stores por ficha guardan bajo su id.
    request.state.user = {"id": payload.get("sub"), "role": role}

    with as_instructor(payload["sub"]):
        return await call_next(request)
