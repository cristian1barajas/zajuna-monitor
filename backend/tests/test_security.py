"""Endurecimiento de la API: secreto, guard por ficha, cabeceras y límites."""
from __future__ import annotations

import time
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from src.api import security
from src.api.auth import CMM_JWT_ALGORITHM, CMM_JWT_SECRET_KEY
from src.api.dependencies import get_snapshot
from src.api.security import SecuritySettings
from src.api.server import app

FICHA = "3389000"
SNAPSHOT = {
    "timestamp": "2026-10-30T05:00:00",
    "courses": [{"ficha": FICHA, "course_id": 1, "students": [], "evidences": []}],
    "summaries": [],
    "participants": [],
    "errors": [],
}


@pytest.fixture
def client():
    app.dependency_overrides[get_snapshot] = lambda: SNAPSHOT
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --- Secreto JWT ---

@pytest.mark.parametrize("weak", ["tu_secreto_que_sea_dificil", "corto", "x" * 31])
def test_secreto_debil_no_arranca(weak):
    with pytest.raises(ValidationError):
        SecuritySettings(cmm_jwt_secret_key=weak)


def test_solo_algoritmos_hmac():
    with pytest.raises(ValidationError):
        SecuritySettings(cmm_jwt_secret_key="k" * 40, cmm_jwt_algorithm="none")


def test_produccion_apaga_herramientas_locales():
    dev = SecuritySettings(cmm_jwt_secret_key="k" * 40)
    prod = SecuritySettings(cmm_jwt_secret_key="k" * 40, app_env="production", cors_origins="https://monitor.example")
    assert dev.local_tools and not prod.local_tools
    assert prod.cors_origin_list == ["https://monitor.example"]
    assert SecuritySettings(cmm_jwt_secret_key="k" * 40, app_env="production", local_tools_enabled=True).local_tools


def _token(**payload) -> str:
    base = {"role": "instructor", "type": "access", "exp": int(time.time()) + 600}
    return jwt.encode({**base, **payload}, CMM_JWT_SECRET_KEY, algorithm=CMM_JWT_ALGORITHM)


def test_token_sin_usuario_se_rechaza(client):
    resp = client.get("/api/dashboard", headers={"Authorization": f"Bearer {_token()}"})
    assert resp.status_code == 401
    resp = client.get("/api/dashboard", headers={"Authorization": f"Bearer {_token(sub='  ')}"})
    assert resp.status_code == 401


def test_token_firmado_con_otro_secreto_se_rechaza(client):
    forged = jwt.encode(
        {"sub": "1", "role": "admin", "type": "access", "exp": int(time.time()) + 600},
        "tu_secreto_que_sea_dificil",
        algorithm="HS256",
    )
    assert client.get("/api/dashboard", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


# --- Guard por ficha ---

def test_ficha_con_caracteres_no_numericos(client):
    for ficha in ["..%5C..%5Cetc", "abc", "3389000.json"]:
        assert client.get(f"/api/fichas/{ficha}/sofia-report").status_code in (400, 404)
    assert client.get("/api/fichas/..%5C..%5Cetc/sofia-report").status_code == 400


def test_ficha_que_no_es_del_instructor(client):
    assert client.get("/api/fichas/1234567/rap-mapping").status_code == 404
    assert client.delete("/api/fichas/1234567/sofia-report").status_code == 404
    # La propia sí pasa el guard (404 aquí es "sin reporte", no "sin acceso").
    resp = client.get(f"/api/fichas/{FICHA}/sofia-report")
    assert resp.status_code in (200, 404)
    assert "no encontrada" not in resp.text


# --- Cabeceras y límites ---

def test_cabeceras_de_seguridad(client):
    resp = client.get("/api/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]


def test_cuerpo_demasiado_grande(client):
    with patch.object(security.get_security_settings(), "max_body_mb", 1):
        resp = client.post(
            f"/api/fichas/{FICHA}/sofia-report",
            content=b"x" * (1024 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 413


def test_limite_de_frecuencia(client):
    security.reset_rate_limits()
    try:
        with patch.object(security.get_security_settings(), "rate_limit_per_minute", 3):
            codes = [client.get("/api/health").status_code for _ in range(4)]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429
    finally:
        security.reset_rate_limits()


def test_importar_telefonos_apagado_fuera_de_local(client):
    with patch.object(security.get_security_settings(), "local_tools_enabled", False):
        resp = client.post("/api/fichas/phone-data/import", json={"folder_path": "C:/"})
    assert resp.status_code == 404
