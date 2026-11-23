"""Tests del cache de respuestas serializadas (src/api/response_cache.py)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api import response_cache
from src.api.dependencies import get_snapshot
from src.api.server import app

from tests.test_api import MOCK_SNAPSHOT


@pytest.fixture
def cached_client(tmp_path, monkeypatch):
    """Client con el cache ACTIVO y un snapshot-file propio para el mtime."""
    fake_snapshot = tmp_path / "latest.json"
    fake_snapshot.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("ZAJUNA_RESPONSE_CACHE", "1")
    from src.api import dependencies as deps

    monkeypatch.setattr(deps, "_snapshot_path", fake_snapshot)
    # Ya no hay fallback al global: el snapshot "del usuario" es este archivo.
    monkeypatch.setattr(deps, "snapshot_path_for", lambda request: fake_snapshot)
    response_cache.clear()

    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with patch(
        "src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT
    ):
        yield TestClient(app)
    app.dependency_overrides.clear()
    response_cache.clear()


class TestResponseCache:
    def test_miss_then_hit(self, cached_client):
        r1 = cached_client.get("/api/dashboard")
        assert r1.status_code == 200
        assert r1.headers["X-Cache"] == "MISS"

        r2 = cached_client.get("/api/dashboard")
        assert r2.status_code == 200
        assert r2.headers["X-Cache"] == "HIT"
        assert r2.json() == r1.json()

    def test_mtime_change_invalidates(self, cached_client, tmp_path):
        cached_client.get("/api/dashboard")
        # Simular un nuevo scrape: cambia el mtime del snapshot
        import os

        from src.api import dependencies as deps

        snap = deps._snapshot_path
        os.utime(snap, (snap.stat().st_atime + 10, snap.stat().st_mtime + 10))

        r = cached_client.get("/api/dashboard")
        assert r.headers["X-Cache"] == "MISS"

    def test_non_cacheable_route_untouched(self, cached_client):
        # health es pública y no está en la allowlist del cache
        r = cached_client.get("/api/health")
        assert "X-Cache" not in r.headers

    def test_gzip_served_when_accepted(self, cached_client):
        # el detalle pesa >1KB en el mock → debe existir variante gzip
        r = cached_client.get(
            "/api/fichas/3388997", headers={"Accept-Encoding": "gzip"}
        )
        assert r.status_code == 200
        # httpx descomprime transparente; verificar el header de encoding
        assert r.headers.get("Content-Encoding") == "gzip"
        assert r.json()["ficha"] == "3388997"


    def test_cache_is_isolated_per_user(self, cached_client):
        """Un instructor JAMÁS debe recibir el cache de otro."""
        from tests.conftest import make_cmm_token

        r1 = cached_client.get("/api/dashboard")
        assert r1.headers["X-Cache"] == "MISS"
        assert cached_client.get("/api/dashboard").headers["X-Cache"] == "HIT"

        # Mismo endpoint, OTRO usuario (sub distinto): no puede ser HIT
        other = {"Authorization": f"Bearer {make_cmm_token(sub='99')}"}
        r3 = cached_client.get("/api/dashboard", headers=other)
        assert r3.headers["X-Cache"] == "MISS"

    def test_query_string_is_part_of_key(self, cached_client):
        r1 = cached_client.get("/api/alerts")
        r2 = cached_client.get("/api/alerts?severity=critical")
        assert r1.headers["X-Cache"] == "MISS"
        assert r2.headers["X-Cache"] == "MISS"  # key distinta, no HIT del anterior
