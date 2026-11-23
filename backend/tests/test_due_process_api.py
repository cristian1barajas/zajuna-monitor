"""Tests for the due process API endpoints."""
from __future__ import annotations

import io
import zipfile
from email import message_from_bytes, policy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.server import app

from tests.conftest import make_cmm_token

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
            "students": [
                {
                    "user_id": 100,
                    "full_name": "JUAN PEREZ",
                    "document": "1234567890",
                    "email": "juan@test.com",
                    "grades": {
                        "1001": {"evidence_id": 1001, "value": "-", "passed": False},
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
                    },
                },
                {
                    "user_id": 102,
                    "full_name": "CARLOS DIAZ",
                    "document": "5555555555",
                    "email": "carlos@test.com",
                    "grades": {
                        "1001": {"evidence_id": 1001, "value": "A", "passed": True},
                        "1002": {"evidence_id": 1002, "value": "A", "passed": True},
                        "1003": {"evidence_id": 1003, "value": "A", "passed": True},
                    },
                },
            ],
        },
    ],
    "summaries": [],
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
                    "last_access_raw": "5 días 2 horas",
                    "last_access_days": 5,
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
            ],
        },
    ],
    "errors": [],
}


@pytest.fixture
def client(tmp_path):
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with (
        patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        patch("src.store.due_process_store.DUE_PROCESS_DIR", tmp_path),
        patch("src.api.routes.due_process.load_due_process") as mock_load,
        patch("src.api.routes.due_process.advance_due_process") as mock_advance,
        patch("src.api.routes.due_process.delete_due_process") as mock_delete,
        patch("src.api.routes.due_process._load_submission_status") as mock_sub,
        patch("src.api.routes.due_process.load_novedades_set") as mock_nov,
    ):
        # By default, no existing records
        mock_load.return_value = None
        mock_advance.return_value = {
            "user_id": 100,
            "full_name": "JUAN PEREZ",
            "document": "1234567890",
            "current_stage": "primer_llamado",
            "history": [
                {
                    "stage": "primer_llamado",
                    "date": "2026-03-01T10:00:00",
                    "evidence_ids": [1001],
                    "evidence_names": ["AA1-EV01 Informe"],
                    "email_generated": True,
                }
            ],
        }
        mock_delete.return_value = True
        # By default, no submitted-but-ungraded cells
        mock_sub.return_value = set()
        # By default, no novedades
        mock_nov.return_value = set()

        with TestClient(app) as c:
            yield c, mock_load, mock_advance, mock_delete, mock_sub, mock_nov
    app.dependency_overrides.clear()


class TestGetDueProcess:
    def test_empty_returns_empty_list(self, client):
        c, mock_load, _, _, _, _ = client
        mock_load.return_value = None
        resp = c.get("/api/due-process/3388997")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert data["records"] == []
        assert data["total_records"] == 0

    def test_returns_existing_records(self, client):
        c, mock_load, _, _, _, _ = client
        mock_load.return_value = {
            "ficha": "3388997",
            "updated_at": "2026-03-01T10:00:00",
            "records": {
                "100": {
                    "user_id": 100,
                    "full_name": "JUAN PEREZ",
                    "document": "1234567890",
                    "current_stage": "primer_llamado",
                    "history": [
                        {
                            "stage": "primer_llamado",
                            "date": "2026-03-01T10:00:00",
                            "evidence_ids": [1001],
                            "evidence_names": ["AA1-EV01 Informe"],
                            "email_generated": True,
                        }
                    ],
                }
            },
        }
        resp = c.get("/api/due-process/3388997")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_records"] == 1
        record = data["records"][0]
        assert record["user_id"] == 100
        assert record["current_stage"] == "primer_llamado"
        assert record["current_stage_label"] == "Primer llamado de atención"
        assert len(record["history"]) == 1


class TestGetStudentDueProcess:
    def test_not_found_no_data(self, client):
        c, mock_load, _, _, _, _ = client
        resp = c.get("/api/due-process/3388997/100")
        assert resp.status_code == 404

    def test_not_found_wrong_user(self, client):
        c, mock_load, _, _, _, _ = client
        mock_load.return_value = {
            "records": {"200": {"user_id": 200, "full_name": "OTHER", "document": "000", "current_stage": "primer_llamado", "history": []}},
        }
        resp = c.get("/api/due-process/3388997/100")
        assert resp.status_code == 404

    def test_returns_student_record(self, client):
        c, mock_load, _, _, _, _ = client
        mock_load.return_value = {
            "records": {
                "100": {
                    "user_id": 100,
                    "full_name": "JUAN PEREZ",
                    "document": "1234567890",
                    "current_stage": "segundo_llamado",
                    "history": [
                        {"stage": "primer_llamado", "date": "2026-02-15", "evidence_ids": [], "evidence_names": [], "email_generated": True},
                        {"stage": "segundo_llamado", "date": "2026-02-20", "evidence_ids": [], "evidence_names": [], "email_generated": True},
                    ],
                }
            },
        }
        resp = c.get("/api/due-process/3388997/100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert data["record"]["current_stage"] == "segundo_llamado"
        assert len(data["record"]["history"]) == 2


class TestEmailDrafts:
    def test_generates_primer_llamado(self, client):
        c, _, _, _, _, _ = client
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [100], "evidence_ids": [1001, 1003]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        draft = data["drafts"][0]
        assert draft["user_id"] == 100
        assert draft["full_name"] == "JUAN PEREZ"
        assert draft["email"] == "juan@test.com"
        assert draft["stage"] == "primer_llamado"
        assert "Primer llamado" in draft["subject"]
        assert "JUAN PEREZ" in draft["body"]

    def test_empty_user_ids_returns_400(self, client):
        c, _, _, _, _, _ = client
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [], "evidence_ids": [1001]},
        )
        assert resp.status_code == 400

    def test_unknown_user_skipped(self, client):
        c, _, _, _, _, _ = client
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [999], "evidence_ids": [1001]},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_multiple_students(self, client):
        """Student 101 is Suspendido, so only student 100 gets a draft."""
        c, _, _, _, _, _ = client
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [100, 101], "evidence_ids": [1001]},
        )
        assert resp.status_code == 200
        # Student 101 is Suspendido in mock data → skipped
        assert resp.json()["total"] == 1
        assert resp.json()["drafts"][0]["user_id"] == 100

    def test_draft_contains_evidence_names(self, client):
        c, _, _, _, _, _ = client
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [100], "evidence_ids": [1001, 1003]},
        )
        body = resp.json()["drafts"][0]["body"]
        assert "AA1-EV01 Informe" in body
        assert "AA2-EV01 Proyecto" in body


class TestAdvance:
    def test_advances_student(self, client):
        c, _, mock_advance, _, _, _ = client
        resp = c.post(
            "/api/due-process/3388997/advance",
            json={"user_ids": [100], "evidence_ids": [1001]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert data["advanced"] == 1
        assert len(data["records"]) == 1
        mock_advance.assert_called_once()

    def test_empty_user_ids_returns_400(self, client):
        c, _, _, _, _, _ = client
        resp = c.post(
            "/api/due-process/3388997/advance",
            json={"user_ids": [], "evidence_ids": [1001]},
        )
        assert resp.status_code == 400


class TestDeleteDueProcess:
    def test_delete_existing(self, client):
        c, _, _, mock_delete, _, _ = client
        mock_delete.return_value = True
        resp = c.delete("/api/due-process/3388997")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_nonexistent(self, client):
        c, _, _, mock_delete, _, _ = client
        mock_delete.return_value = False
        resp = c.delete("/api/due-process/9999999")
        assert resp.status_code == 404


class TestEmailFiltering:
    """Tests for per-student evidence filtering in email drafts."""

    def test_only_pending_evidences_included(self, client):
        """Student 100 has 1001(-) and 1003(-), not 1002. All should appear."""
        c, _, _, _, _, _ = client
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [100], "evidence_ids": [1001, 1002, 1003]},
        )
        body = resp.json()["drafts"][0]["body"]
        assert "AA1-EV01 Informe" in body   # 1001: value="-"
        assert "AA1-EV02 Taller" in body    # 1002: no grade → included
        assert "AA2-EV01 Proyecto" in body  # 1003: value="-"

    def test_approved_student_excluded_from_drafts(self, client):
        """Student 102 has all evidences approved → should be skipped entirely."""
        c, _, _, _, _, _ = client
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [102], "evidence_ids": [1001, 1002, 1003]},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_yellow_cell_excluded(self, client):
        """Yellow cell exclusion: student 100 evidence 1001 marked as yellow → excluded."""
        c, _, _, _, mock_sub, _ = client
        # Mark 1001:100 as submitted-but-ungraded (yellow)
        mock_sub.return_value = {"1001:100"}
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [100], "evidence_ids": [1001]},
        )
        # Student 100 only requested evidence 1001, which is yellow → skip student
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_mixed_yellow_and_pending(self, client):
        """Student 100 has 1001(-) and 1003(-). If 1001 is yellow, only 1003 in email."""
        c, _, _, _, mock_sub, _ = client
        mock_sub.return_value = {"1001:100"}
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [100], "evidence_ids": [1001, 1003]},
        )
        assert resp.json()["total"] == 1
        body = resp.json()["drafts"][0]["body"]
        assert "AA1-EV01 Informe" not in body  # yellow → excluded
        assert "AA2-EV01 Proyecto" in body      # pending → included

    def test_disapproved_included(self, client):
        """Disapproved evidence (D) should be included in the email."""
        c, _, _, _, _, _ = client
        # Temporarily modify snapshot — student 100 has 1001 as "D"
        import copy
        modified = copy.deepcopy(MOCK_SNAPSHOT)
        modified["courses"][0]["students"][0]["grades"]["1001"]["value"] = "D"
        app.dependency_overrides[get_snapshot] = lambda: modified

        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [100], "evidence_ids": [1001]},
        )
        assert resp.json()["total"] == 1
        body = resp.json()["drafts"][0]["body"]
        assert "AA1-EV01 Informe" in body  # D → included

        # Restore
        app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT


class TestNovedadExclusion:
    """Tests that students with novedades are excluded from emails and advances."""

    def test_novedad_student_excluded_from_email(self, client):
        """Student with novedad should not get email draft."""
        c, _, _, _, _, mock_nov = client
        mock_nov.return_value = {100}  # Student 100 has novedad
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [100], "evidence_ids": [1001, 1003]},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_novedad_student_excluded_from_advance(self, client):
        """Student with novedad should not be advanced."""
        c, _, mock_advance, _, _, mock_nov = client
        mock_nov.return_value = {100}
        resp = c.post(
            "/api/due-process/3388997/advance",
            json={"user_ids": [100], "evidence_ids": [1001]},
        )
        assert resp.status_code == 200
        assert resp.json()["advanced"] == 0
        mock_advance.assert_not_called()

    def test_mixed_novedad_and_normal(self, client):
        """Student 100 has novedad, 101 is Suspendido → both excluded, 0 drafts."""
        c, _, _, _, _, mock_nov = client
        mock_nov.return_value = {100}  # Only 100 has novedad
        resp = c.post(
            "/api/due-process/3388997/email-drafts",
            json={"user_ids": [100, 101], "evidence_ids": [1001]},
        )
        assert resp.status_code == 200
        # 100 excluded by novedad, 101 excluded by Suspendido status
        assert resp.json()["total"] == 0


# --- Exportar borradores como .eml (Outlook) ---


def _payload(*user_ids: int) -> dict:
    return {
        "drafts": [
            {
                "user_id": uid,
                "full_name": "JUAN PÉREZ",
                "email": "juan@test.com",
                "subject": "Primer llamado de atención",
                "body": "Cuerpo con ñ y tildes: acción.",
                "stage": "primer_llamado",
            }
            for uid in user_ids
        ]
    }


EML_URL = "/api/due-process/3388997/email-drafts/eml"


class TestEmlEndpoint:
    def test_un_borrador_devuelve_eml(self, client):
        c, *_ = client
        resp = c.post(EML_URL, json=_payload(100))
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("message/rfc822")
        assert (
            resp.headers["content-disposition"]
            == 'attachment; filename="01 - Primer llamado - JUAN PEREZ.eml"'
        )
        msg = message_from_bytes(resp.content, policy=policy.default)
        assert msg["X-Unsent"] == "1"
        assert msg["To"] == "juan@test.com"
        assert msg["Subject"] == "Primer llamado de atención"

    def test_varios_borradores_devuelven_zip(self, client):
        c, *_ = client
        resp = c.post(EML_URL, json=_payload(100, 101))
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        disposition = resp.headers["content-disposition"]
        assert disposition.startswith('attachment; filename="correos-llamados-ficha-3388997-')
        assert disposition.endswith('.zip"')
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            assert len(zf.namelist()) == 2

    def test_as_zip_con_un_borrador_devuelve_zip(self, client):
        c, *_ = client
        resp = c.post(EML_URL, json={**_payload(100), "as_zip": True})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            assert zf.namelist() == ["01 - Primer llamado - JUAN PEREZ.eml"]

    def test_lista_vacia_es_422(self, client):
        c, *_ = client
        assert c.post(EML_URL, json={"drafts": []}).status_code == 422

    def test_aprendiz_ajeno_a_la_ficha_es_400(self, client):
        c, *_ = client
        resp = c.post(EML_URL, json=_payload(100, 999))
        assert resp.status_code == 400

    def test_ficha_no_visible_es_404(self, client):
        c, *_ = client
        resp = c.post("/api/due-process/9999999/email-drafts/eml", json=_payload(100))
        assert resp.status_code == 404

    def test_sin_token_es_401(self, client):
        c, *_ = client
        resp = c.post(EML_URL, json=_payload(100), headers={"Authorization": ""})
        assert resp.status_code == 401

    def test_rol_no_permitido_es_403(self, client):
        c, *_ = client
        token = make_cmm_token(role="aprendiz")
        resp = c.post(EML_URL, json=_payload(100), headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
