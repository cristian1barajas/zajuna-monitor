"""Tests for the Zajuna Monitor API endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_base_config, get_snapshot
from src.api.server import app

# --- Fixtures ---

MOCK_SNAPSHOT = {
    "timestamp": "2026-03-01T05:00:12",
    "instructor_id": 718455,
    "courses": [
        {
            "course_id": 89977,
            "course_name": "ANALISIS Y DESARROLLO DE SOFTWARE. (3388997)",
            "ficha": "3388997",
            "evidences": [
                {"item_id": 1001, "name": "AA1-EV01 Informe", "category": "Fase 1 Analisis"},
                {"item_id": 1002, "name": "AA1-EV02 Taller", "category": "Fase 1 Analisis"},
                {"item_id": 1003, "name": "AA2-EV01 Proyecto", "category": "Fase 2 Planeacion"},
            ],
            "students": [
                {
                    "user_id": 100,
                    "full_name": "JUAN PEREZ",
                    "document": "1234567890",
                    "email": "juan@test.com",
                    "grades": {
                        "1001": {"evidence_id": 1001, "value": "A", "passed": True},
                        "1002": {"evidence_id": 1002, "value": "D", "passed": False},
                        "1003": {"evidence_id": 1003, "value": "-", "passed": False},
                    },
                },
                {
                    "user_id": 101,
                    "full_name": "MARIA GOMEZ",
                    "document": "0987654321",
                    "email": "maria@test.com",
                    "grades": {
                        "1001": {"evidence_id": 1001, "value": "-", "passed": False},
                        "1002": {"evidence_id": 1002, "value": "-", "passed": False},
                        "1003": {"evidence_id": 1003, "value": "-", "passed": False},
                    },
                },
            ],
            "scraped_at": "2026-03-01T05:00:15",
        },
    ],
    "summaries": [
        {
            "course_id": 89977,
            "ficha": "3388997",
            "total_students": 2,
            "total_evidences": 3,
            "total_approved": 1,
            "total_disapproved": 1,
            "total_pending": 4,
            "pending_by_evidence": {"1001": 1, "1002": 1, "1003": 2},
            "completion_percentage": 33.3,
        },
    ],
    "participants": [
        {
            "course_id": 89977,
            "ficha": "3388997",
            "participants": [
                {
                    "user_id": 100,
                    "full_name": "JUAN PEREZ",
                    "document": "1234567890",
                    "email": "juan@test.com",
                    "role": "Aprendiz",
                    "groups": "No hay grupos",
                    "last_access_raw": "12 días 17 horas",
                    "last_access_days": 12,
                    "status": "Activo",
                },
                {
                    "user_id": 101,
                    "full_name": "MARIA GOMEZ",
                    "document": "0987654321",
                    "email": "maria@test.com",
                    "role": "Aprendiz",
                    "groups": "No hay grupos",
                    "last_access_raw": "47 días",
                    "last_access_days": 47,
                    "status": "Suspendido",
                },
                {
                    "user_id": 102,
                    "full_name": "PEDRO MARTINEZ",
                    "document": "5555555555",
                    "email": "pedro@test.com",
                    "role": "Aprendiz",
                    "groups": "Grupo A",
                    "last_access_raw": "2 horas 30 minutos",
                    "last_access_days": 0,
                    "status": "Activo",
                },
            ],
            "scraped_at": "2026-03-01T05:00:20",
        },
    ],
    "errors": [],
    "metadata": {
        "version": "1.0.0",
        "duration_seconds": 8.4,
        "total_courses": 1,
        "total_errors": 0,
        "total_requests": 4,
    },
}


@pytest.fixture
def client():
    """TestClient with mocked snapshot (no auth enforcement)."""
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with (
        patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        TestClient(app) as c,
    ):
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client():
    """TestClient with API key enforcement."""
    mock_cfg = MagicMock()
    mock_cfg.api_key = "test-secret-key"

    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    app.dependency_overrides[get_base_config] = lambda: mock_cfg
    with (
        patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        TestClient(app) as c,
    ):
        yield c
    app.dependency_overrides.clear()


# --- Health ---

class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["courses_count"] == 1
        assert data["errors_count"] == 0

    def test_health_has_last_scrape(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert data["last_scrape"] is not None


# --- Dashboard ---

class TestDashboard:
    def test_dashboard_returns_summary(self, client):
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        # total_students = todos (JUAN 100 activo + MARIA 101 suspendida)
        assert data["total_students"] == 2
        assert data["total_evidences"] == 3
        # pendientes solo de activos: JUAN tiene 1 ("-" en evidencia 1003);
        # los 3 pendientes de MARIA (suspendida) se excluyen
        assert data["total_pending"] == 1
        assert len(data["fichas"]) == 1

    def test_dashboard_ficha_item(self, client):
        resp = client.get("/api/dashboard")
        ficha = resp.json()["fichas"][0]
        assert ficha["ficha"] == "3388997"
        assert ficha["course_id"] == 89977
        assert ficha["total_students"] == 2  # todos
        assert ficha["total_active"] == 1  # solo JUAN
        assert ficha["total_pending"] == 1  # pendientes de activos

    def test_dashboard_has_alerts_count(self, client):
        resp = client.get("/api/dashboard")
        data = resp.json()
        assert "alerts_count" in data
        assert isinstance(data["alerts_count"], int)


# --- Fichas ---

class TestFichas:
    def test_list_fichas(self, client):
        resp = client.get("/api/fichas")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ficha"] == "3388997"

    def test_ficha_detail(self, client):
        resp = client.get("/api/fichas/3388997")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert data["course_id"] == 89977
        assert len(data["students"]) == 2
        assert len(data["evidences"]) == 3

    def test_ficha_detail_active_only_metrics(self, client):
        resp = client.get("/api/fichas/3388997")
        data = resp.json()
        # total_students = todos (2), total_active = solo JUAN (1)
        assert data["total_students"] == 2
        assert data["total_active"] == 1
        # avance solo de activos: JUAN tiene 2/3 calificadas → 66.7%
        assert data["completion_percentage"] == 66.7

    def test_list_fichas_active_only(self, client):
        resp = client.get("/api/fichas")
        ficha = resp.json()[0]
        assert ficha["total_students"] == 2
        assert ficha["total_active"] == 1
        assert ficha["total_pending"] == 1  # solo pendientes de JUAN

    def test_ficha_detail_student_stats(self, client):
        resp = client.get("/api/fichas/3388997")
        students = resp.json()["students"]
        juan = next(s for s in students if s["full_name"] == "JUAN PEREZ")
        assert juan["approved"] == 1
        assert juan["disapproved"] == 1
        assert juan["pending"] == 1

    def test_ficha_detail_evidence_stats(self, client):
        resp = client.get("/api/fichas/3388997")
        evidences = resp.json()["evidences"]
        # Solo activos: JUAN aprobó 1001; el "-" de MARIA (suspendida) no cuenta
        ev1 = next(e for e in evidences if e["item_id"] == 1001)
        assert ev1["total_approved"] == 1
        assert ev1["total_pending"] == 0

    def test_ficha_not_found(self, client):
        resp = client.get("/api/fichas/9999999")
        assert resp.status_code == 404

    def test_ficha_pendientes(self, client):
        resp = client.get("/api/fichas/3388997/pendientes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        # Solo activos: JUAN tiene pendiente 1003; MARIA (suspendida) se excluye
        assert data["by_evidence"][0]["item_id"] == 1003
        assert data["by_evidence"][0]["pending_count"] == 1
        assert len(data["by_student"]) == 1

    def test_pendientes_sorted_by_count(self, client):
        resp = client.get("/api/fichas/3388997/pendientes")
        by_ev = resp.json()["by_evidence"]
        counts = [e["pending_count"] for e in by_ev]
        assert counts == sorted(counts, reverse=True)

    def test_pendientes_excludes_suspended(self, client):
        resp = client.get("/api/fichas/3388997/pendientes")
        by_st = resp.json()["by_student"]
        # MARIA (suspendida) NO aparece aunque tenga 3 pendientes; solo JUAN
        names = [s["full_name"] for s in by_st]
        assert "MARIA GOMEZ" not in names
        assert by_st[0]["full_name"] == "JUAN PEREZ"
        assert by_st[0]["pending_count"] == 1


# --- Alerts ---

class TestAlerts:
    def test_alerts_endpoint(self, client):
        resp = client.get("/api/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert "total" in data
        assert isinstance(data["alerts"], list)

    @staticmethod
    def _cronograma(cutoff: str):
        """Cronograma de la ficha 3388997 con la evidencia 1003 cerrando en ``cutoff``."""
        return patch(
            "src.api.alerts.load_cronograma",
            side_effect=lambda ficha: {
                "ficha": ficha,
                "entries": [
                    {"evidence_name": "AA2-EV01", "evidence_item_id": 1003, "cutoff_date": cutoff}
                ],
            },
        )

    def test_alerts_zero_graded(self, client):
        # Evidence 1003 has 2/2 pending = 100% = zero_graded, and it already closed
        with self._cronograma("2026-01-31"):
            alerts = client.get("/api/alerts").json()["alerts"]
        zero = [a for a in alerts if a["type"] == "zero_graded"]
        assert len(zero) >= 1
        assert zero[0]["severity"] == "critical"

    def test_evidence_alerts_carry_item_id(self, client):
        """El front enlaza cada alerta de evidencia con Por Calificar por su item_id."""
        with self._cronograma("2026-01-31"):
            alerts = client.get("/api/alerts").json()["alerts"]
        zero = next(a for a in alerts if a["type"] == "zero_graded")
        assert zero["item_id"] == 1003
        course_alerts = [a for a in alerts if a["type"] == "low_completion"]
        assert all(a["item_id"] is None for a in course_alerts)

    def test_no_alert_for_evidence_that_closes_later(self, client):
        with self._cronograma("2999-12-31"):
            alerts = client.get("/api/alerts").json()["alerts"]
        assert not [a for a in alerts if a["item_id"] == 1003]

    def test_without_cronograma_skips_evidences_after_the_last_graded_one(self, client):
        """1003 comes after 1002, the last evidence with a grade: not reached yet."""
        with patch("src.api.alerts.load_cronograma", return_value=None):
            alerts = client.get("/api/alerts").json()["alerts"]
        assert not [a for a in alerts if a["item_id"] == 1003]

    def test_alerts_filter_by_ficha(self, client):
        resp = client.get("/api/alerts?ficha=3388997")
        data = resp.json()
        assert all(a["ficha"] == "3388997" for a in data["alerts"])

    def test_alerts_filter_by_severity(self, client):
        resp = client.get("/api/alerts?severity=critical")
        data = resp.json()
        assert all(a["severity"] == "critical" for a in data["alerts"])

    def test_alerts_filter_nonexistent_ficha(self, client):
        resp = client.get("/api/alerts?ficha=0000000")
        data = resp.json()
        assert data["total"] == 0


# --- Snapshot ---

class TestSnapshot:
    def test_snapshot_latest(self, client):
        resp = client.get("/api/snapshot/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert "courses" in data
        assert "summaries" in data
        assert "timestamp" in data


# --- Auth ---

class TestAuth:
    def test_no_api_key_rejected(self, auth_client):
        resp = auth_client.get("/api/dashboard")
        assert resp.status_code == 401

    def test_wrong_api_key_rejected(self, auth_client):
        resp = auth_client.get("/api/dashboard", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_correct_api_key_accepted(self, auth_client):
        resp = auth_client.get("/api/dashboard", headers={"X-API-Key": "test-secret-key"})
        assert resp.status_code == 200

    def test_health_no_auth_required(self, client):
        """Health endpoint should work without API key."""
        resp = client.get("/api/health")
        assert resp.status_code == 200


# --- Activity ---

class TestActivity:
    def test_activity_summary(self, client):
        resp = client.get("/api/activity")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert item["ficha"] == "3388997"
        assert item["total_participants"] == 3
        assert item["total_active"] == 2
        assert item["total_suspended"] == 1

    def test_activity_summary_avg_days(self, client):
        resp = client.get("/api/activity")
        item = resp.json()[0]
        # (12 + 47 + 0) / 3 = 19.7
        assert item["avg_days_since_access"] == 19.7

    def test_activity_summary_inactive_30_plus(self, client):
        resp = client.get("/api/activity")
        item = resp.json()[0]
        # Only MARIA (47 days) is 30+
        assert item["inactive_30_plus"] == 1

    def test_activity_detail(self, client):
        resp = client.get("/api/activity/3388997")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert len(data["participants"]) == 3
        assert data["total_active"] == 2
        assert data["total_suspended"] == 1

    def test_activity_detail_participant_fields(self, client):
        resp = client.get("/api/activity/3388997")
        p = resp.json()["participants"][0]
        assert "user_id" in p
        assert "full_name" in p
        assert "document" in p
        assert "email" in p
        assert "last_access_raw" in p
        assert "last_access_days" in p
        assert "status" in p

    def test_activity_detail_filter_inactive(self, client):
        resp = client.get("/api/activity/3388997?min_days_inactive=30")
        assert resp.status_code == 200
        data = resp.json()
        # Only MARIA (47 days) should pass the filter
        assert len(data["participants"]) == 1
        assert data["participants"][0]["full_name"] == "MARIA GOMEZ"

    def test_activity_detail_not_found(self, client):
        resp = client.get("/api/activity/9999999")
        assert resp.status_code == 404
