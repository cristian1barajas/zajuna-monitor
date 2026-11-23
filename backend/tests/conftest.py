"""Configuración compartida de la suite de tests.

El middleware ``cmm_auth_middleware`` (src/api/auth.py) exige un JWT del
Sistema CMM en todo ``/api/*`` (excepto rutas públicas). Los tests existentes
crean sus propios ``TestClient(app)`` sin token, así que aquí se parchea
``TestClient.__init__`` para que TODOS los clientes de la suite envíen por
defecto un ``Authorization: Bearer <token>`` válido, sin tocar cada test.

Los tests que necesitan ejercitar el middleware sin token (o con otro rol)
pueden eliminar/sobrescribir el header en su propio client
(ver tests/test_cmm_auth_middleware.py).
"""
from __future__ import annotations

import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient

# La API no arranca sin un secreto fuerte: si el entorno no trae uno (CI o una
# máquina sin backend/.env), los tests usan uno propio. Va antes de importar la app.
os.environ.setdefault("CMM_JWT_SECRET_KEY", "tests-" + "0123456789abcdef" * 4)
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from src.api.auth import CMM_JWT_ALGORITHM, CMM_JWT_SECRET_KEY  # noqa: E402

# El cache de respuestas sirve bytes keyed por mtime de data/latest.json;
# los tests mockean el snapshot vía dependency_overrides (el archivo real no
# cambia entre tests), así que se desactiva para evitar respuestas cruzadas.
os.environ["ZAJUNA_RESPONSE_CACHE"] = "0"


def make_cmm_token(
    sub: str = "1",
    role: str = "instructor",
    expires_in: int = 3600,
    token_type: str = "access",
) -> str:
    """Genera un JWT firmado como lo haría el backend CMM (HS256)."""
    payload = {
        "sub": sub,
        "role": role,
        "exp": int(time.time()) + expires_in,
        "type": token_type,
    }
    return jwt.encode(payload, CMM_JWT_SECRET_KEY, algorithm=CMM_JWT_ALGORITHM)


@pytest.fixture(autouse=True)
def _instructor_de_prueba():
    """Los stores por ficha guardan por instructor. El token por defecto es del
    instructor "1": lo que un test guarde directo en un store lo ve la API."""
    from src.store.instructor_scope import as_instructor

    with as_instructor("1"):
        yield


@pytest.fixture
def cmm_token() -> str:
    """Token CMM válido (rol instructor) para tests que lo necesiten explícito."""
    return make_cmm_token()


# --- Autenticación por defecto para todos los TestClient de la suite ---

_original_testclient_init = TestClient.__init__


def _authenticated_testclient_init(self, *args, **kwargs):
    _original_testclient_init(self, *args, **kwargs)
    # No pisar un Authorization definido explícitamente por el test.
    if "Authorization" not in self.headers:
        self.headers["Authorization"] = f"Bearer {make_cmm_token()}"


TestClient.__init__ = _authenticated_testclient_init
