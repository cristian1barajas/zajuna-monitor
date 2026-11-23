"""Tests for the scraper trigger API endpoints."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.server import app
from src.scraper.job_manager import ScraperJob, ScraperStep

MOCK_SNAPSHOT = {
    "timestamp": "2026-03-01T05:00:12",
    "courses": [
        {"course_id": 89977, "ficha": "3388997", "course_name": "ADSO (3388997)"},
        {"course_id": 89967, "ficha": "3388998", "course_name": "ADSO (3388998)"},
    ],
    "summaries": [],
    "participants": [],
    "errors": [],
}


@pytest.fixture
def client():
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestScraperStatus:
    def test_status_idle_when_no_job(self, client):
        with patch("src.api.routes.scraper.job_manager") as mock_jm:
            mock_jm.get_current_job.return_value = None
            resp = client.get("/api/scraper/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["job_id"] is None
        assert data["steps"] == []

    def test_status_returns_running_job(self, client):
        job = ScraperJob(
            job_id="abc123",
            status="running",
            started_at="2026-03-02T10:00:00",
            progress="Ficha 3388997 — calificaciones",
            courses_total=2,
            courses_done=0,
            steps=[
                ScraperStep(label="Autenticacion", status="completed"),
                ScraperStep(label="Ficha 3388997 — calificaciones", status="running"),
                ScraperStep(label="Ficha 3388997 — participantes", status="pending"),
            ],
        )
        with patch("src.api.routes.scraper.job_manager") as mock_jm:
            mock_jm.get_current_job.return_value = job
            resp = client.get("/api/scraper/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["job_id"] == "abc123"
        assert data["courses_total"] == 2
        assert len(data["steps"]) == 3
        assert data["steps"][0]["status"] == "completed"
        assert data["steps"][1]["status"] == "running"

    def test_status_returns_completed_job(self, client):
        job = ScraperJob(
            job_id="def456",
            status="completed",
            started_at="2026-03-02T10:00:00",
            finished_at="2026-03-02T10:01:15",
            progress="Completado",
            courses_total=2,
            courses_done=2,
            duration_seconds=75.3,
            steps=[
                ScraperStep(label="Autenticacion", status="completed"),
                ScraperStep(label="Ficha 3388997 — calificaciones", status="completed"),
            ],
        )
        with patch("src.api.routes.scraper.job_manager") as mock_jm:
            mock_jm.get_current_job.return_value = job
            resp = client.get("/api/scraper/status")
        data = resp.json()
        assert data["status"] == "completed"
        assert data["duration_seconds"] == 75.3
        assert data["finished_at"] is not None

    def test_status_returns_failed_job(self, client):
        job = ScraperJob(
            job_id="ghi789",
            status="failed",
            started_at="2026-03-02T10:00:00",
            finished_at="2026-03-02T10:00:05",
            progress="Error: AuthError",
            courses_total=2,
            courses_done=0,
            error="Authentication failed",
            duration_seconds=5.1,
            steps=[
                ScraperStep(label="Autenticacion", status="failed"),
            ],
        )
        with patch("src.api.routes.scraper.job_manager") as mock_jm:
            mock_jm.get_current_job.return_value = job
            resp = client.get("/api/scraper/status")
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error"] == "Authentication failed"


class TestScraperTrigger:
    def test_trigger_all_fichas(self, client):
        mock_job = ScraperJob(
            job_id="new123",
            status="running",
            started_at="2026-03-02T10:00:00",
            progress="Iniciando...",
            courses_total=5,
            steps=[],
        )
        with (
            patch("src.api.routes.scraper.job_manager") as mock_jm,
            patch("src.api.routes.scraper.tracked_store.tracked_course_ids", return_value=[14897, 14903]),
        ):
            mock_jm.is_running.return_value = False
            mock_jm.start_job.return_value = mock_job
            resp = client.post("/api/scraper/run", json={"fichas": None})
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "running"
        assert data["job_id"] == "new123"

    def test_sin_grupos_registrados_no_usa_los_del_env(self, client):
        # Los ZAJUNA_COURSE_IDS del .env son de quien instaló el monitor.
        with (
            patch("src.api.routes.scraper.job_manager") as mock_jm,
            patch("src.api.routes.scraper.tracked_store.tracked_course_ids", return_value=None),
        ):
            mock_jm.is_running.return_value = False
            resp = client.post("/api/scraper/run", json={"fichas": None})
        assert resp.status_code == 400
        mock_jm.start_job.assert_not_called()

    def test_trigger_single_ficha(self, client):
        mock_job = ScraperJob(
            job_id="single1",
            status="running",
            started_at="2026-03-02T10:00:00",
            progress="Iniciando...",
            courses_total=1,
            steps=[],
        )
        with (
            patch("src.api.routes.scraper.job_manager") as mock_jm,
            # La resolución ficha→curso lee el snapshot del disco, no el
            # override de get_snapshot; se parchea para no depender del
            # data/ local del desarrollador.
            patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        ):
            mock_jm.is_running.return_value = False
            mock_jm.start_job.return_value = mock_job
            resp = client.post("/api/scraper/run", json={"fichas": ["3388997"]})
        assert resp.status_code == 202
        # Verify start_job was called with the resolved course_id
        mock_jm.start_job.assert_called_once()
        call_args = mock_jm.start_job.call_args
        assert 89977 in call_args[0][1]  # course_ids arg

    def test_trigger_conflict_when_running(self, client):
        with patch("src.api.routes.scraper.job_manager") as mock_jm:
            mock_jm.is_running.return_value = True
            resp = client.post("/api/scraper/run", json={})
        assert resp.status_code == 409
        assert "already running" in resp.json()["detail"]

    def test_trigger_unknown_ficha_falls_back(self, client):
        mock_job = ScraperJob(
            job_id="fb1",
            status="running",
            started_at="2026-03-02T10:00:00",
            progress="Iniciando...",
            courses_total=0,
            steps=[],
        )
        with (
            patch("src.api.routes.scraper.job_manager") as mock_jm,
            patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        ):
            mock_jm.is_running.return_value = False
            mock_jm.start_job.return_value = mock_job
            resp = client.post("/api/scraper/run", json={"fichas": ["9999999"]})
        # Unknown ficha resolves to empty list → 400
        assert resp.status_code == 400

    def test_response_has_all_fields(self, client):
        mock_job = ScraperJob(
            job_id="fields1",
            status="running",
            started_at="2026-03-02T10:00:00",
            progress="Test",
            courses_total=1,
            steps=[ScraperStep(label="Test step", status="pending")],
        )
        with (
            patch("src.api.routes.scraper.job_manager") as mock_jm,
            patch("src.api.routes.scraper.tracked_store.tracked_course_ids", return_value=[14897]),
        ):
            mock_jm.is_running.return_value = False
            mock_jm.start_job.return_value = mock_job
            resp = client.post("/api/scraper/run", json={})
        data = resp.json()
        assert "job_id" in data
        assert "status" in data
        assert "progress" in data
        assert "courses_total" in data
        assert "courses_done" in data
        assert "started_at" in data
        assert "steps" in data
        assert data["steps"][0]["label"] == "Test step"
