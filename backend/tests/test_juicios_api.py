"""Tests for juicios API endpoints."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.server import app

MOCK_SNAPSHOT = {
    "timestamp": "2026-03-01T05:00:12",
    "courses": [
        {
            "course_id": 89977,
            "ficha": "3388997",
            "course_name": "ADSO",
            "evidences": [
                {"item_id": 100, "name": "GA1-220501092-AA1-EV01 Infografia"},
                {"item_id": 101, "name": "GA1-220501092-AA1-EV02 Taller"},
            ],
            "students": [
                {
                    "user_id": 1,
                    "full_name": "JUAN BAEZ",
                    "document": "1000000007",
                    "email": "juan@test.com",
                    "grades": {
                        "100": {"value": "A", "passed": True},
                        "101": {"value": "A", "passed": True},
                    },
                },
            ],
        },
    ],
    "summaries": [],
    "participants": [],
    "errors": [],
}


@pytest.fixture
def client(tmp_path):
    """TestClient with mocked snapshot and temp store dirs."""
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT), \
         patch("src.store.rap_mapping_store.RAP_MAPPINGS_DIR", tmp_path / "rap"), \
         patch("src.store.sofia_store.SOFIA_REPORTS_DIR", tmp_path / "sofia"), TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


RAP_MAPPING_BODY = {
    "program_name": "ADSO",
    "mappings": [
        {
            "fase": "ANALISIS",
            "competencia": "220501092 - ANALIZAR LOS REQUISITOS",
            "rap": "220501092-01 - INTERPRETAR",
            "evidencias": [
                {"code": "GA1-220501092-AA1-EV01", "name": "Infografia"},
                {"code": "GA1-220501092-AA1-EV02", "name": "Taller"},
            ],
        },
    ],
    "stats": {
        "total_raps": 1,
        "total_evidencias": 2,
        "matched_evidencias": 0,
        "unmatched_evidencias": 2,
    },
}

SOFIA_REPORT_BODY = {
    "program_name": "ADSO",
    "total_students": 1,
    "total_raps": 1,
    "students": [
        {
            "document": "1000000007",
            "full_name": "JUAN BAEZ",
            "student_status": "EN FORMACION",
            "judgments": [
                {
                    "competencia_code": "38392",
                    "competencia_desc": "ANALIZAR LOS REQUISITOS",
                    "rap_code": "593060",
                    "rap_desc": "01 INTERPRETAR",
                    "juicio": "POR EVALUAR",
                },
            ],
        },
    ],
    "competency_map": {
        "38392 - ANALIZAR LOS REQUISITOS": "220501092 - ANALIZAR LOS REQUISITOS",
    },
}


class TestRapMappingAPI:
    def test_get_empty_returns_404(self, client):
        resp = client.get("/api/fichas/3388997/rap-mapping")
        assert resp.status_code == 404

    def test_post_and_get(self, client):
        resp = client.post("/api/fichas/3388997/rap-mapping", json=RAP_MAPPING_BODY)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert data["program_name"] == "ADSO"
        assert len(data["mappings"]) == 1
        # Should resolve item_ids from snapshot
        ev1 = data["mappings"][0]["evidencias"][0]
        assert ev1["item_id"] == 100
        assert ev1["matched"] is True

        # GET should return same
        resp = client.get("/api/fichas/3388997/rap-mapping")
        assert resp.status_code == 200
        assert resp.json()["ficha"] == "3388997"

    def test_delete(self, client):
        client.post("/api/fichas/3388997/rap-mapping", json=RAP_MAPPING_BODY)
        resp = client.delete("/api/fichas/3388997/rap-mapping")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        resp = client.get("/api/fichas/3388997/rap-mapping")
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/fichas/9999999/rap-mapping")
        assert resp.status_code == 404


class TestSofiaReportAPI:
    def test_get_empty_returns_404(self, client):
        resp = client.get("/api/fichas/3388997/sofia-report")
        assert resp.status_code == 404

    def test_post_and_get(self, client):
        resp = client.post("/api/fichas/3388997/sofia-report", json=SOFIA_REPORT_BODY)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert data["total_students"] == 1
        assert data["students_count"] == 1

        resp = client.get("/api/fichas/3388997/sofia-report")
        assert resp.status_code == 200

    def test_delete(self, client):
        client.post("/api/fichas/3388997/sofia-report", json=SOFIA_REPORT_BODY)
        resp = client.delete("/api/fichas/3388997/sofia-report")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/fichas/9999999/sofia-report")
        assert resp.status_code == 404


class TestRapCrossAPI:
    def test_cross_missing_rap_mapping(self, client):
        client.post("/api/fichas/3388997/sofia-report", json=SOFIA_REPORT_BODY)
        resp = client.get("/api/fichas/3388997/rap-cross")
        assert resp.status_code == 404
        assert "RAP mapping" in resp.json()["detail"]

    def test_cross_missing_sofia_report(self, client):
        client.post("/api/fichas/3388997/rap-mapping", json=RAP_MAPPING_BODY)
        resp = client.get("/api/fichas/3388997/rap-cross")
        assert resp.status_code == 404
        assert "Sofia report" in resp.json()["detail"]

    def test_cross_full(self, client):
        client.post("/api/fichas/3388997/rap-mapping", json=RAP_MAPPING_BODY)
        client.post("/api/fichas/3388997/sofia-report", json=SOFIA_REPORT_BODY)
        resp = client.get("/api/fichas/3388997/rap-cross")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert data["total_students"] >= 1

    def test_cross_filter_document(self, client):
        client.post("/api/fichas/3388997/rap-mapping", json=RAP_MAPPING_BODY)
        client.post("/api/fichas/3388997/sofia-report", json=SOFIA_REPORT_BODY)
        resp = client.get("/api/fichas/3388997/rap-cross?document=1000000007")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_students"] == 1
