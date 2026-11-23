"""Tests for novedades (administrative novelties) API."""
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
            "course_name": "ANALISIS Y DESARROLLO DE SOFTWARE. (3388997)",
            "ficha": "3388997",
            "evidences": [],
            "students": [
                {
                    "user_id": 100,
                    "full_name": "JUAN PEREZ",
                    "document": "1234567890",
                    "email": "juan@test.com",
                    "grades": {},
                },
                {
                    "user_id": 101,
                    "full_name": "MARIA GOMEZ",
                    "document": "0987654321",
                    "email": "maria@test.com",
                    "grades": {},
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
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with (
        patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        patch("src.store.novedades_store.NOVEDADES_DIR", tmp_path),
        TestClient(app) as c,
    ):
        yield c
    app.dependency_overrides.clear()


class TestGetNovedades:
    def test_empty_returns_empty(self, client):
        resp = client.get("/api/fichas/3388997/novedades")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert data["total"] == 0
        assert data["records"] == []
        assert "cancelacion" in data["types"]

    def test_returns_existing_records(self, client):
        # First add a novedad
        client.post(
            "/api/fichas/3388997/novedades",
            json={"user_ids": [100], "type": "cancelacion", "note": "Queja enviada"},
        )
        resp = client.get("/api/fichas/3388997/novedades")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        rec = data["records"][0]
        assert rec["user_id"] == 100
        assert rec["full_name"] == "JUAN PEREZ"
        assert rec["type"] == "cancelacion"
        assert rec["note"] == "Queja enviada"


class TestAddNovedades:
    def test_add_single(self, client):
        resp = client.post(
            "/api/fichas/3388997/novedades",
            json={"user_ids": [100], "type": "cancelacion", "note": "Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["records"][0]["user_id"] == 100
        assert data["records"][0]["type_label"] == "Cancelacion en proceso"

    def test_add_multiple(self, client):
        resp = client.post(
            "/api/fichas/3388997/novedades",
            json={"user_ids": [100, 101], "type": "cancelacion"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_empty_user_ids_returns_400(self, client):
        resp = client.post(
            "/api/fichas/3388997/novedades",
            json={"user_ids": [], "type": "cancelacion"},
        )
        assert resp.status_code == 400

    def test_invalid_type_returns_400(self, client):
        resp = client.post(
            "/api/fichas/3388997/novedades",
            json={"user_ids": [100], "type": "invalid_type"},
        )
        assert resp.status_code == 400

    def test_update_existing_preserves_created_at(self, client):
        # Add first time
        resp1 = client.post(
            "/api/fichas/3388997/novedades",
            json={"user_ids": [100], "type": "cancelacion", "note": "First"},
        )
        created_at = resp1.json()["records"][0]["created_at"]

        # Update
        resp2 = client.post(
            "/api/fichas/3388997/novedades",
            json={"user_ids": [100], "type": "cancelacion", "note": "Updated"},
        )
        rec = resp2.json()["records"][0]
        assert rec["created_at"] == created_at
        assert rec["note"] == "Updated"


class TestRemoveNovedades:
    def test_remove(self, client):
        # Add first
        client.post(
            "/api/fichas/3388997/novedades",
            json={"user_ids": [100, 101], "type": "cancelacion"},
        )
        # Remove one
        resp = client.post(
            "/api/fichas/3388997/novedades/remove",
            json={"user_ids": [100]},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["records"][0]["user_id"] == 101

    def test_remove_empty_returns_400(self, client):
        resp = client.post(
            "/api/fichas/3388997/novedades/remove",
            json={"user_ids": []},
        )
        assert resp.status_code == 400


class TestDeleteAllNovedades:
    def test_delete_existing(self, client):
        client.post(
            "/api/fichas/3388997/novedades",
            json={"user_ids": [100], "type": "cancelacion"},
        )
        resp = client.delete("/api/fichas/3388997/novedades")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/fichas/9999999/novedades")
        assert resp.status_code == 404
