"""Aislamiento entre instructores: datos por ficha, cuenta Zajuna y sincronización."""
from __future__ import annotations

import threading
from unittest.mock import patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from src.api import dependencies
from src.api.dependencies import get_snapshot
from src.api.server import app
from src.scraper import job_manager
from src.store.instructor_scope import (
    as_instructor,
    current_instructor,
    start_thread,
    validate_user_id,
)
from src.store.sofia_store import load_sofia_report, save_sofia_report

from tests.conftest import make_cmm_token

FICHA = "3389000"  # el mismo grupo para los dos instructores
ANA, BETO = "10", "20"


def _snapshot(students: list[dict]) -> dict:
    return {
        "timestamp": "2026-10-30T05:00:00",
        "courses": [{"ficha": FICHA, "course_id": 1, "course_name": "ADSO", "students": students, "evidences": []}],
        "summaries": [],
        "participants": [],
        "errors": [],
    }


SNAPSHOTS = {
    ANA: _snapshot([{"user_id": 1, "full_name": "APRENDIZ UNO", "document": "1", "grades": {}}]),
    BETO: _snapshot([{"user_id": 2, "full_name": "APRENDIZ DOS", "document": "2", "grades": {}}]),
}


def _snapshot_del_usuario(request: Request) -> dict:
    return SNAPSHOTS[request.state.user["id"]]


@pytest.fixture
def stores(tmp_path):
    with (
        patch("src.store.sofia_store.SOFIA_REPORTS_DIR", tmp_path / "sofia_reports"),
        patch("src.store.novedades_store.NOVEDADES_DIR", tmp_path / "novedades"),
    ):
        yield tmp_path


@pytest.fixture
def client(stores):
    app.dependency_overrides[get_snapshot] = _snapshot_del_usuario
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _as(user_id: str) -> dict:
    return {"Authorization": f"Bearer {make_cmm_token(sub=user_id)}"}


def test_mismo_grupo_datos_separados(client, stores):
    with as_instructor(ANA):
        save_sofia_report(FICHA, {"program_name": "ADSO", "students": [], "competency_map": {}})

    assert client.get(f"/api/fichas/{FICHA}/sofia-report", headers=_as(ANA)).status_code == 200
    assert client.get(f"/api/fichas/{FICHA}/sofia-report", headers=_as(BETO)).status_code == 404
    # Borrar el suyo no toca el de Ana.
    client.delete(f"/api/fichas/{FICHA}/sofia-report", headers=_as(BETO))
    with as_instructor(ANA):
        assert load_sofia_report(FICHA) is not None
    assert (stores / "sofia_reports" / ANA / f"{FICHA}.json").exists()


def test_novedades_de_un_instructor_no_las_ve_otro(client):
    resp = client.post(f"/api/fichas/{FICHA}/novedades", json={"user_ids": [1]}, headers=_as(ANA))
    assert resp.status_code == 200 and resp.json()["total"] == 1
    assert client.get(f"/api/fichas/{FICHA}/novedades", headers=_as(BETO)).json()["total"] == 0
    assert client.get(f"/api/fichas/{FICHA}/novedades", headers=_as(ANA)).json()["total"] == 1


def test_cada_instructor_usa_su_cuenta_de_zajuna(client):
    cuentas = {ANA: {"type_document": "CC", "document": "111", "password": "clave-ana"}}
    vistas: list[str] = []

    def fake_client(config):
        vistas.append(config.zajuna_document)
        raise RuntimeError("sin red en tests")

    with (
        patch("src.store.zajuna_accounts_store.get_account_credentials", side_effect=cuentas.get),
        patch("src.api.routes.download_evidences._get_client", side_effect=fake_client),
        pytest.raises(RuntimeError),
    ):
        client.get(f"/api/fichas/{FICHA}/submissions/5", headers=_as(ANA))
    assert vistas == ["111"]

    # Beto no tiene cuenta: no se usa la de Ana ni la del .env.
    with patch("src.store.zajuna_accounts_store.get_account_credentials", side_effect=cuentas.get):
        resp = client.get(f"/api/fichas/{FICHA}/submissions/5", headers=_as(BETO))
    assert resp.status_code == 409


def test_sincronizacion_por_instructor():
    liberar = threading.Event()

    def scrape_lento(*_args, **_kwargs):
        liberar.wait(5)

    with patch("src.scraper.job_manager.scrape_courses", side_effect=scrape_lento):
        job_manager.start_job(dependencies.get_base_config(), [1], cmm_user_id=ANA)
        try:
            assert job_manager.is_running(ANA)
            assert not job_manager.is_running(BETO)
            assert job_manager.get_current_job(BETO) is None
            with pytest.raises(RuntimeError):
                job_manager.start_job(dependencies.get_base_config(), [1], cmm_user_id=ANA)
        finally:
            liberar.set()


def test_hilos_heredan_el_instructor():
    visto: list[str | None] = []
    with as_instructor(ANA):
        start_thread(lambda: visto.append(current_instructor.get())).join(5)
    assert visto == [ANA]


@pytest.mark.parametrize("malo", ["..", "../2", "a/b", "a\\b", "", "x" * 65])
def test_id_de_instructor_no_arma_rutas_raras(malo):
    with pytest.raises(ValueError):
        validate_user_id(malo)


def test_token_con_sub_raro_se_rechaza(client):
    assert client.get("/api/dashboard", headers=_as("../2")).status_code == 401


def test_migracion_mueve_solo_archivos_de_ficha(tmp_path):
    from scripts import migrar_datos_por_instructor as mig

    store = tmp_path / "sofia_reports"
    store.mkdir()
    (store / "3389000.json").write_text("{}", encoding="utf-8")
    (store / "notas.txt").write_text("", encoding="utf-8")
    (store / "2").mkdir()
    (store / "2" / "3607707.json").write_text("{}", encoding="utf-8")
    (store / "3607707.json").write_text("{}", encoding="utf-8")  # destino ya existe

    with patch.object(mig, "STORE_DIRS", [store]), patch.object(mig, "DATA_DIR", tmp_path):
        assert mig.main(["2", "--aplicar"]) == 0
    assert (store / "2" / "3389000.json").exists() and not (store / "3389000.json").exists()
    assert (store / "notas.txt").exists()
    assert (store / "3607707.json").exists()  # no se pisa el que ya estaba

    with patch.object(mig, "STORE_DIRS", [store]), patch.object(mig, "DATA_DIR", tmp_path):
        mig.main(["2", "--revertir", "--aplicar"])
    assert (store / "3389000.json").exists()
