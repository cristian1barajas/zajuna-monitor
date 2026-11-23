"""Tests del módulo "Agregar grupo": descubrimiento, registro y resolución."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from src.api.server import app
from src.auth.manager import AuthError, ZajunaUnavailableError
from src.parsers.my_courses import DiscoveredCourse, MyCoursesResult
from src.scraper.job_manager import ScraperJob
from src.store import tracked_courses_store as tracked_store

USER_ID = "1"  # sub del token que inyecta conftest.make_cmm_token()

CREDS = {"type_document": "CC", "document": "0000000000", "password": "x"}

DISCOVERED = MyCoursesResult(
    courses=[
        DiscoveredCourse(89977, "P_228118_V_3388997_R_11_C_9214",
                         "ANALISIS Y DESARROLLO DE SOFTWARE", "3388997", "228118"),
        DiscoveredCourse(99001, "P_233104_V_3607707_R_11_C_9214",
                         "PROGRAMACION DE SOFTWARE", "3607707", "233104"),
        DiscoveredCourse(99002, "SALA-INSTRUCTORES", "ESPACIO DE INSTRUCTORES", "", ""),
    ],
    truncated=False,
)

TPS_COURSE = {
    "course_id": 99001,
    "ficha": "3607707",
    "shortname": "P_233104_V_3607707_R_11_C_9214",
    "fullname": "PROGRAMACION DE SOFTWARE",
    "program_code": "233104",
}


@pytest.fixture(autouse=True)
def isolated_instructor_dir(tmp_path):
    """El registro escribe en tmp, nunca en backend/data del desarrollador."""
    with patch(
        "src.store.tracked_courses_store.instructor_data_dir",
        lambda uid: tmp_path / "instructors" / str(uid),
    ):
        yield tmp_path


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ─── Store ────────────────────────────────────────────────────────────────


class TestTrackedStore:
    def test_no_registry_returns_none(self):
        assert tracked_store.load_tracked(USER_ID) is None
        assert tracked_store.tracked_course_ids(USER_ID) is None
        assert tracked_store.load_tracked(None) is None

    def test_save_keeps_added_at_of_existing_courses(self):
        first = tracked_store.save_tracked(USER_ID, [TPS_COURSE])
        second = tracked_store.save_tracked(
            USER_ID, [TPS_COURSE, {**TPS_COURSE, "course_id": 89977, "ficha": "3388997"}]
        )
        assert second[0]["added_at"] == first[0]["added_at"]
        assert tracked_store.tracked_course_ids(USER_ID) == [99001, 89977]

    def test_lookups(self):
        tracked_store.save_tracked(USER_ID, [TPS_COURSE])
        assert tracked_store.ficha_for_course(USER_ID, 99001) == "3607707"
        assert tracked_store.ficha_for_course(USER_ID, 1) is None
        assert tracked_store.course_ids_for_fichas(USER_ID, ["3607707", "9"]) == {"3607707": 99001}


# ─── GET /api/courses/discover ────────────────────────────────────────────


class TestDiscover:
    def test_requires_connected_account(self, client):
        with patch("src.api.routes.courses.vault.get_account_credentials", return_value=None):
            r = client.get("/api/courses/discover")
        assert r.status_code == 409

    def test_lists_courses_with_program_and_tracked_flag(self, client):
        tracked_store.save_tracked(USER_ID, [TPS_COURSE])
        with (
            patch("src.api.routes.courses.vault.get_account_credentials", return_value=CREDS),
            patch("src.api.routes.courses.discover_courses", return_value=DISCOVERED) as disc,
        ):
            r = client.get("/api/courses/discover")

        assert r.status_code == 200
        # Se usan las credenciales DEL instructor autenticado
        assert disc.call_args[0][0].zajuna_document == CREDS["document"]
        data = r.json()
        assert data["truncated"] is False
        by_id = {c["course_id"]: c for c in data["courses"]}
        assert by_id[99001]["tracked"] is True
        assert by_id[99001]["program_label"] == "TPS"
        assert by_id[89977]["tracked"] is False
        assert by_id[89977]["program_label"] == "ADSO"
        assert by_id[99002]["ficha"] == ""
        assert by_id[99002]["program_label"] == "ESPACIO DE INSTRUCTORES"

    def test_rejected_credentials_mark_account_invalid(self, client):
        with (
            patch("src.api.routes.courses.vault.get_account_credentials", return_value=CREDS),
            patch("src.api.routes.courses.vault.mark_status") as mark,
            patch("src.api.routes.courses.discover_courses", side_effect=AuthError("bad")),
        ):
            r = client.get("/api/courses/discover")
        assert r.status_code == 400
        mark.assert_called_once_with(USER_ID, "invalid")

    def test_zajuna_down_is_502_and_keeps_account(self, client):
        with (
            patch("src.api.routes.courses.vault.get_account_credentials", return_value=CREDS),
            patch("src.api.routes.courses.vault.mark_status") as mark,
            patch(
                "src.api.routes.courses.discover_courses",
                side_effect=ZajunaUnavailableError("down"),
            ),
        ):
            r = client.get("/api/courses/discover")
        assert r.status_code == 502
        mark.assert_not_called()


# ─── GET/POST /api/courses/tracked ────────────────────────────────────────


class TestTracked:
    def test_get_without_registry(self, client):
        r = client.get("/api/courses/tracked")
        assert r.status_code == 200
        assert r.json() == {"configured": False, "courses": []}

    def test_save_and_read_back(self, client):
        r = client.post("/api/courses/tracked", json={"courses": [TPS_COURSE]})
        assert r.status_code == 200
        saved = r.json()
        assert saved["configured"] is True
        assert saved["courses"][0]["ficha"] == "3607707"
        assert saved["courses"][0]["program_label"] == "TPS"

        r = client.get("/api/courses/tracked")
        assert [c["course_id"] for c in r.json()["courses"]] == [99001]

    def test_rejects_course_without_valid_ficha(self, client):
        r = client.post(
            "/api/courses/tracked",
            json={"courses": [{**TPS_COURSE, "ficha": ""}]},
        )
        assert r.status_code == 422

    def test_rejects_duplicated_ficha(self, client):
        r = client.post(
            "/api/courses/tracked",
            json={"courses": [TPS_COURSE, {**TPS_COURSE, "course_id": 99003}]},
        )
        assert r.status_code == 400
        assert "3607707" in r.json()["detail"]


# ─── Resolución en POST /api/scraper/run ──────────────────────────────────


def _job() -> ScraperJob:
    return ScraperJob(job_id="j1", status="running", started_at="2026-10-16T10:00:00",
                      progress="Iniciando...", courses_total=1, steps=[])


class TestScraperUsesRegistry:
    def test_new_ficha_without_snapshot_can_be_synced(self, client):
        """El caso del grupo nuevo: está en el registro pero no en ningún snapshot."""
        tracked_store.save_tracked(USER_ID, [TPS_COURSE])
        no_snapshot = HTTPException(status_code=503, detail="No snapshot")
        with (
            patch("src.api.routes.scraper.job_manager") as jm,
            patch("src.api.dependencies.load_snapshot", side_effect=no_snapshot),
        ):
            jm.is_running.return_value = False
            jm.start_job.return_value = _job()
            r = client.post("/api/scraper/run", json={"fichas": ["3607707"]})
        assert r.status_code == 202
        assert jm.start_job.call_args[0][1] == [99001]

    def test_unknown_ficha_without_snapshot_is_400_not_all_courses(self, client):
        """Antes, sin snapshot se caía a TODOS los cursos del .env."""
        no_snapshot = HTTPException(status_code=503, detail="No snapshot")
        with (
            patch("src.api.routes.scraper.job_manager") as jm,
            patch("src.api.dependencies.load_snapshot", side_effect=no_snapshot),
        ):
            jm.is_running.return_value = False
            r = client.post("/api/scraper/run", json={"fichas": ["9999999"]})
        assert r.status_code == 400
        jm.start_job.assert_not_called()

    def test_sync_all_uses_registry_over_env(self, client):
        tracked_store.save_tracked(USER_ID, [TPS_COURSE])
        with patch("src.api.routes.scraper.job_manager") as jm:
            jm.is_running.return_value = False
            jm.start_job.return_value = _job()
            r = client.post("/api/scraper/run", json={"fichas": None})
        assert r.status_code == 202
        assert jm.start_job.call_args[0][1] == [99001]


class TestCronUsesRegistry:
    def test_course_ids_for_prefers_registry(self, isolated_instructor_dir):
        from src.main import _course_ids_for

        tracked_store.save_tracked(USER_ID, [TPS_COURSE])
        with patch("src.main.instructor_data_dir", lambda uid: isolated_instructor_dir / "x"):
            assert _course_ids_for(USER_ID, config=None) == [99001]
