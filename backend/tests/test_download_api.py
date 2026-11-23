"""Tests for download evidences API endpoints."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_base_config, get_config, get_snapshot
from src.api.server import app
from src.client.zajuna import FetchError

FIXTURES = Path(__file__).parent / "fixtures"

MOCK_SNAPSHOT = {
    "timestamp": "2026-03-01T05:00:12",
    # El guard por ficha solo deja pasar grupos que estén en el snapshot.
    "courses": [{"ficha": "3388997", "course_id": 89977, "students": [], "evidences": []}],
    "summaries": [],
    "participants": [],
    "errors": [],
}

MOCK_ASSIGNMENTS = {
    "ficha": "3388997",
    "course_id": 89977,
    "updated_at": "2026-03-05T10:30:00",
    "assignments": [
        {"name": "GA1-220501046-AA2-EV01 Taller", "cmid": 5967181, "item_id": 100, "module_type": "assign"},
    ],
}


@pytest.fixture
def submissions_html() -> str:
    return (FIXTURES / "assignment_submissions_sample.html").read_text(encoding="utf-8")


@pytest.fixture
def instrument_html() -> str:
    return (FIXTURES / "assignment_detail_with_instrument.html").read_text(encoding="utf-8")


@pytest.fixture
def client_with_mock(submissions_html, instrument_html):
    """TestClient with mocked Zajuna authentication and HTTP calls."""
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    # Zajuna va mockeado: basta la config del .env, sin cuenta del vault.
    app.dependency_overrides[get_config] = get_base_config

    mock_auth = MagicMock()
    mock_client = MagicMock()
    mock_client.fetch_submissions_list.return_value = submissions_html
    mock_client.fetch_assignment_detail.return_value = instrument_html

    with (
        patch("src.api.routes.download_evidences._get_client", return_value=(mock_auth, mock_client)),
        TestClient(app) as c,
    ):
        yield c, mock_client

    app.dependency_overrides.clear()


class TestGetSubmissions:
    def test_returns_submissions_list(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.get("/api/fichas/3388997/submissions/5967181")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cmid"] == 5967181
        assert data["ficha"] == "3388997"

    def test_returns_all_entries(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.get("/api/fichas/3388997/submissions/5967181")
        data = resp.json()
        assert data["total_submissions"] == 6
        assert len(data["submissions"]) == 6

    def test_submission_has_expected_fields(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.get("/api/fichas/3388997/submissions/5967181")
        sub = resp.json()["submissions"][0]
        assert "user_id" in sub
        assert "full_name" in sub
        assert "document" in sub
        assert "email" in sub
        assert "status" in sub
        assert "is_graded" in sub
        assert "file_count" in sub

    def test_returns_unique_statuses(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.get("/api/fichas/3388997/submissions/5967181")
        data = resp.json()
        assert "Enviado para calificar" in data["statuses"]
        assert "Sin entrega" in data["statuses"]

    def test_instrument_available(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.get("/api/fichas/3388997/submissions/5967181")
        data = resp.json()
        assert data["instrument_available"] is True

    def test_assignment_name_extracted(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.get("/api/fichas/3388997/submissions/5967181")
        data = resp.json()
        assert "GA1-220501046-AA2-EV01" in data["assignment_name"]


class TestStartDownload:
    def test_returns_job_id(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.post(
            "/api/fichas/3388997/download-evidence",
            json={
                "cmid": 5967181,
                "target_dir": "C:/tmp/test",
                "include_instrument": True,
                "status_filter": ["Enviado para calificar"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert len(data["job_id"]) > 0


class TestDownloadStatus:
    def test_nonexistent_job_returns_404(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.get("/api/fichas/3388997/download-status/nonexistent")
        assert resp.status_code == 404


def _wait_for_batch(client, job_id: str) -> dict:
    """Poll the batch job until it leaves pending/running (max ~3 s)."""
    for _ in range(60):
        data = client.get(f"/api/fichas/3388997/download-pending-status/{job_id}").json()
        if data["status"] not in ("pending", "running"):
            return data
        time.sleep(0.05)
    raise AssertionError(f"Batch job did not finish: {data}")


class TestDownloadPending:
    def test_rejects_empty_cmid_list(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.post(
            "/api/fichas/3388997/download-pending",
            json={"cmids": [], "target_dir": "C:/tmp/test"},
        )
        assert resp.status_code == 422

    def test_downloads_only_pending_submissions_of_each_cmid(self, client_with_mock, tmp_path):
        client, mock_client = client_with_mock
        mock_client.download_file.return_value = (b"contenido", "entrega.pdf")

        resp = client.post(
            "/api/fichas/3388997/download-pending",
            json={"cmids": [5967181, 5967182], "target_dir": str(tmp_path), "include_instrument": False},
        )
        assert resp.status_code == 200
        data = _wait_for_batch(client, resp.json()["job_id"])

        assert data["status"] == "completed"
        assert [i["cmid"] for i in data["items"]] == [5967181, 5967182]
        # The fixture has one submission sent for grading and not graded yet
        assert all(i["status"] == "completed" and i["downloaded"] == 1 for i in data["items"])
        assert data["downloaded"] == 2
        assert mock_client.fetch_submissions_list.call_count == 2

    def test_failed_assignment_does_not_stop_the_batch(self, client_with_mock, submissions_html, tmp_path):
        client, mock_client = client_with_mock
        mock_client.download_file.return_value = (b"contenido", "entrega.pdf")
        mock_client.fetch_submissions_list.side_effect = [
            FetchError("Zajuna no respondió"),
            submissions_html,
        ]

        resp = client.post(
            "/api/fichas/3388997/download-pending",
            json={"cmids": [1, 2], "target_dir": str(tmp_path), "include_instrument": False},
        )
        data = _wait_for_batch(client, resp.json()["job_id"])

        first, second = data["items"]
        assert first["status"] == "failed"
        assert first["errors"]
        assert second["status"] == "completed"

    def test_unknown_batch_job_returns_404(self, client_with_mock):
        client, _ = client_with_mock
        resp = client.get("/api/fichas/3388997/download-pending-status/nonexistent")
        assert resp.status_code == 404
