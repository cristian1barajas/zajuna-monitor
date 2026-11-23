"""Tests for cronograma store and API endpoints."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.server import app
from src.store.cronograma_store import (
    delete_cronograma,
    load_cronograma,
    save_cronograma,
)

# --- Store tests ---

class TestCronogramaStore:
    def test_save_and_load(self, tmp_path):
        with patch("src.store.cronograma_store.CRONOGRAMAS_DIR", tmp_path):
            entries = [
                {"evidence_name": "AA1-EV01", "evidence_item_id": 1001, "cutoff_date": "2026-02-15"},
                {"evidence_name": "AA1-EV02", "evidence_item_id": 1002, "cutoff_date": "2026-03-01"},
            ]
            result = save_cronograma("3388997", entries)
            assert result["ficha"] == "3388997"
            assert len(result["entries"]) == 2
            assert "updated_at" in result

            loaded = load_cronograma("3388997")
            assert loaded is not None
            assert loaded["ficha"] == "3388997"
            assert len(loaded["entries"]) == 2

    def test_load_nonexistent(self, tmp_path):
        with patch("src.store.cronograma_store.CRONOGRAMAS_DIR", tmp_path):
            result = load_cronograma("9999999")
            assert result is None

    def test_delete_existing(self, tmp_path):
        with patch("src.store.cronograma_store.CRONOGRAMAS_DIR", tmp_path):
            save_cronograma("3388997", [{"evidence_name": "EV01", "cutoff_date": "2026-01-01"}])
            assert delete_cronograma("3388997") is True
            assert load_cronograma("3388997") is None

    def test_delete_nonexistent(self, tmp_path):
        with patch("src.store.cronograma_store.CRONOGRAMAS_DIR", tmp_path):
            assert delete_cronograma("9999999") is False

    def test_save_overwrites(self, tmp_path):
        with patch("src.store.cronograma_store.CRONOGRAMAS_DIR", tmp_path):
            save_cronograma("3388997", [{"evidence_name": "EV01", "cutoff_date": "2026-01-01"}])
            save_cronograma("3388997", [
                {"evidence_name": "EV01", "cutoff_date": "2026-02-01"},
                {"evidence_name": "EV02", "cutoff_date": "2026-03-01"},
            ])
            loaded = load_cronograma("3388997")
            assert len(loaded["entries"]) == 2
            assert loaded["entries"][0]["cutoff_date"] == "2026-02-01"

    def test_creates_directory(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        with patch("src.store.cronograma_store.CRONOGRAMAS_DIR", nested):
            save_cronograma("3388997", [])
            assert nested.exists()

    def test_file_content_is_valid_json(self, tmp_path):
        with patch("src.store.cronograma_store.CRONOGRAMAS_DIR", tmp_path):
            save_cronograma("3388997", [{"evidence_name": "EV01", "cutoff_date": "2026-01-01"}])
            # Guarda en la carpeta del instructor (el "1" de los tests)
            raw = (tmp_path / "1" / "3388997.json").read_text(encoding="utf-8")
            data = json.loads(raw)
            assert data["ficha"] == "3388997"


# --- API tests ---

MOCK_SNAPSHOT = {
    "timestamp": "2026-03-01T05:00:12",
    "courses": [
        {
            "course_id": 89977,
            "course_name": "ANALISIS Y DESARROLLO DE SOFTWARE. (3388997)",
            "ficha": "3388997",
            "evidences": [
                {"item_id": 1001, "name": "AA1-EV01 Informe", "category": "Fase 1"},
                {"item_id": 1002, "name": "AA1-EV02 Taller", "category": "Fase 1"},
                {"item_id": 1003, "name": "AA2-EV01 Proyecto", "category": "Fase 2"},
            ],
            "students": [],
        },
    ],
    "summaries": [],
    "participants": [],
    "errors": [],
}


@pytest.fixture
def client(tmp_path):
    """TestClient with mocked snapshot and temp cronograma dir."""
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with (
        patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        patch("src.store.cronograma_store.CRONOGRAMAS_DIR", tmp_path),
        TestClient(app) as c,
    ):
        yield c
    app.dependency_overrides.clear()


class TestCronogramaAPI:
    def test_get_empty_returns_404(self, client):
        resp = client.get("/api/cronograma/3388997")
        assert resp.status_code == 404

    def test_post_and_get(self, client):
        body = {
            "ficha": "3388997",
            "entries": [
                {"evidence_name": "AA1-EV01 Informe", "cutoff_date": "2026-02-15"},
                {"evidence_name": "AA2-EV01 Proyecto", "cutoff_date": "2026-03-01"},
            ],
        }
        resp = client.post("/api/cronograma/3388997", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert len(data["entries"]) == 2
        assert data["entries"][0]["evidence_item_id"] == 1001
        assert data["entries"][1]["evidence_item_id"] == 1003

        # GET should return the same
        resp = client.get("/api/cronograma/3388997")
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) == 2

    def test_post_resolves_partial_name(self, client):
        body = {
            "ficha": "3388997",
            "entries": [
                {"evidence_name": "AA1-EV01", "cutoff_date": "2026-02-15"},
            ],
        }
        resp = client.post("/api/cronograma/3388997", json=body)
        assert resp.status_code == 200
        # "AA1-EV01" is contained in "AA1-EV01 Informe"
        assert resp.json()["entries"][0]["evidence_item_id"] == 1001

    def test_post_unresolved_name(self, client):
        body = {
            "ficha": "3388997",
            "entries": [
                {"evidence_name": "NONEXISTENT-EV99", "cutoff_date": "2026-02-15"},
            ],
        }
        resp = client.post("/api/cronograma/3388997", json=body)
        assert resp.status_code == 200
        assert resp.json()["entries"][0]["evidence_item_id"] is None

    def test_post_overwrites(self, client):
        body1 = {
            "ficha": "3388997",
            "entries": [{"evidence_name": "AA1-EV01", "cutoff_date": "2026-01-01"}],
        }
        client.post("/api/cronograma/3388997", json=body1)

        body2 = {
            "ficha": "3388997",
            "entries": [
                {"evidence_name": "AA1-EV01", "cutoff_date": "2026-02-01"},
                {"evidence_name": "AA1-EV02", "cutoff_date": "2026-03-01"},
            ],
        }
        resp = client.post("/api/cronograma/3388997", json=body2)
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) == 2

    def test_delete(self, client):
        body = {
            "ficha": "3388997",
            "entries": [{"evidence_name": "AA1-EV01", "cutoff_date": "2026-02-15"}],
        }
        client.post("/api/cronograma/3388997", json=body)

        resp = client.delete("/api/cronograma/3388997")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        resp = client.get("/api/cronograma/3388997")
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/cronograma/9999999")
        assert resp.status_code == 404

    def test_response_has_updated_at(self, client):
        body = {
            "ficha": "3388997",
            "entries": [{"evidence_name": "AA1-EV01", "cutoff_date": "2026-02-15"}],
        }
        resp = client.post("/api/cronograma/3388997", json=body)
        assert "updated_at" in resp.json()
        assert resp.json()["updated_at"] != ""
