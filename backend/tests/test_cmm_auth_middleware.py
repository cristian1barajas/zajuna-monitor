"""Tests del middleware de autenticación CMM (src/api/auth.py)."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.server import app

from tests.conftest import make_cmm_token

MOCK_SNAPSHOT = {"courses": [], "errors": [], "metadata": {}}


@pytest.fixture
def anon_client():
    """TestClient SIN header Authorization (elimina el default de conftest)."""
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with (
        patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        TestClient(app) as c,
    ):
        del c.headers["Authorization"]
        yield c
    app.dependency_overrides.clear()


class TestCmmAuthMiddleware:
    def test_sin_token_devuelve_401(self, anon_client):
        resp = anon_client.get("/api/dashboard")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "No autenticado"}
        assert resp.headers["WWW-Authenticate"] == "Bearer"

    def test_token_invalido_devuelve_401(self, anon_client):
        resp = anon_client.get(
            "/api/dashboard", headers={"Authorization": "Bearer no-es-un-jwt"}
        )
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Token inválido"}

    def test_token_expirado_devuelve_401(self, anon_client):
        token = make_cmm_token(expires_in=-60)
        resp = anon_client.get(
            "/api/dashboard", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Token expirado"}

    def test_rol_aprendiz_devuelve_403(self, anon_client):
        token = make_cmm_token(role="aprendiz")
        resp = anon_client.get(
            "/api/dashboard", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403
        assert "aprendiz" in resp.json()["detail"]

    def test_token_instructor_permite_acceso(self, anon_client):
        token = make_cmm_token(role="instructor")
        resp = anon_client.get(
            "/api/dashboard", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200

    def test_health_sin_token_devuelve_200(self, anon_client):
        resp = anon_client.get("/api/health")
        assert resp.status_code == 200


class TestHealthIdentificaAlInstructor:
    """/api/health es pública, pero con token debe leer el snapshot del instructor."""

    @pytest.fixture
    def snapshots(self, tmp_path):
        global_path = tmp_path / "latest.json"
        global_path.write_text('{"timestamp": "2026-07-17T05:00:00", "courses": []}', encoding="utf-8")
        own_dir = tmp_path / "instructors" / "2"
        own_dir.mkdir(parents=True)
        (own_dir / "latest.json").write_text(
            '{"timestamp": "2026-10-24T13:26:07", "courses": [{}]}', encoding="utf-8"
        )
        with (
            patch("src.api.dependencies._snapshot_path", global_path),
            patch("src.api.dependencies.instructor_data_dir", lambda uid: tmp_path / "instructors" / str(uid)),
            # Sin registro de grupos seguidos: se ve el snapshot completo
            patch(
                "src.store.tracked_courses_store.instructor_data_dir",
                lambda uid: tmp_path / "instructors" / str(uid),
            ),
            TestClient(app) as c,
        ):
            del c.headers["Authorization"]
            yield c

    def test_con_token_reporta_el_snapshot_del_instructor(self, snapshots):
        token = make_cmm_token(sub="2")
        resp = snapshots.get("/api/health", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["last_scrape"].startswith("2026-10-24")
        assert resp.json()["courses_count"] == 1

    def test_sin_token_no_revela_el_snapshot(self, snapshots):
        resp = snapshots.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "last_scrape": None, "courses_count": 0, "errors_count": 0}

    def test_token_invalido_no_bloquea_health(self, snapshots):
        resp = snapshots.get("/api/health", headers={"Authorization": "Bearer no-es-un-jwt"})
        assert resp.status_code == 200
        assert resp.json()["last_scrape"] is None

    def test_instructor_sin_snapshot_propio_no_ve_el_global(self, snapshots):
        token = make_cmm_token(sub="99")
        assert snapshots.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"}).status_code == 503
        resp = snapshots.get("/api/health", headers={"Authorization": f"Bearer {token}"})
        assert resp.json()["last_scrape"] is None
