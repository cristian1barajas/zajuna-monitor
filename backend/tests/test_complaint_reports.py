"""Tests for complaint reports (Informes de Queja) endpoints."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.server import app


def _fake_docx2pdf_convert(src_dir, dst_dir):
    """Reemplaza docx2pdf.convert: requiere MS Word vía COM (solo Windows,
    y flaky si Word está abierto). Escribe un PDF dummy por cada docx."""
    for f in Path(src_dir).glob("*.docx"):
        Path(dst_dir, f.stem + ".pdf").write_bytes(b"%PDF-1.4 fake")

MOCK_SNAPSHOT = {
    "timestamp": "2026-03-01T05:00:12",
    "instructor_id": 718455,
    "courses": [
        {
            "course_id": 89977,
            "ficha": "3388997",
            "course_name": "ANALISIS Y DESARROLLO DE SOFTWARE",
            "evidences": [
                {"item_id": 1001, "name": "AA1-EV01 Informe", "category": "Fase 1 Analisis"},
                {"item_id": 1002, "name": "AA1-EV02 Taller", "category": "Fase 1 Analisis"},
                {"item_id": 1003, "name": "AA2-EV01 Diagrama", "category": "Fase 2 Diseño"},
            ],
            "students": [
                {
                    "user_id": 100,
                    "full_name": "JUAN PEREZ",
                    "document": "1234567890",
                    "email": "juan@mail.com",
                    "grades": {
                        "1001": {"evidence_id": 1001, "value": "-", "passed": False},
                        "1002": {"evidence_id": 1002, "value": "-", "passed": False},
                        "1003": {"evidence_id": 1003, "value": "-", "passed": False},
                    },
                },
                {
                    "user_id": 101,
                    "full_name": "MARIA GARCIA",
                    "document": "0987654321",
                    "email": "maria@mail.com",
                    "grades": {
                        "1001": {"evidence_id": 1001, "value": "A", "passed": True},
                        "1002": {"evidence_id": 1002, "value": "-", "passed": False},
                        "1003": {"evidence_id": 1003, "value": "A", "passed": True},
                    },
                },
                {
                    "user_id": 102,
                    "full_name": "PEDRO LOPEZ",
                    "document": "1112223334",
                    "email": "pedro@mail.com",
                    "grades": {
                        "1001": {"evidence_id": 1001, "value": "A", "passed": True},
                        "1002": {"evidence_id": 1002, "value": "A", "passed": True},
                        "1003": {"evidence_id": 1003, "value": "A", "passed": True},
                    },
                },
            ],
            "scraped_at": "2026-03-01T05:00:12",
        },
    ],
    "summaries": [
        {
            "course_id": 89977,
            "ficha": "3388997",
            "total_students": 3,
            "total_evidences": 3,
            "total_approved": 5,
            "total_disapproved": 0,
            "total_pending": 4,
            "pending_by_evidence": {"1001": 1, "1002": 2, "1003": 1},
            "completion_percentage": 55.6,
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
                    "email": "juan@mail.com",
                    "role": "Aprendiz",
                    "groups": "No hay grupos",
                    "last_access_raw": "25 días 3 horas",
                    "last_access_days": 25,
                    "status": "Activo",
                },
                {
                    "user_id": 101,
                    "full_name": "MARIA GARCIA",
                    "document": "0987654321",
                    "email": "maria@mail.com",
                    "role": "Aprendiz",
                    "groups": "No hay grupos",
                    "last_access_raw": "5 días 2 horas",
                    "last_access_days": 5,
                    "status": "Activo",
                },
                {
                    "user_id": 102,
                    "full_name": "PEDRO LOPEZ",
                    "document": "1112223334",
                    "email": "pedro@mail.com",
                    "role": "Aprendiz",
                    "groups": "No hay grupos",
                    "last_access_raw": "30 días 1 hora",
                    "last_access_days": 30,
                    "status": "Activo",
                },
            ],
            "scraped_at": "2026-03-01T05:00:12",
        },
    ],
    "errors": [],
    "metadata": {},
}


@pytest.fixture
def client():
    """TestClient with mocked snapshot."""
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with (
        patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        TestClient(app) as c,
    ):
        yield c
    app.dependency_overrides.clear()


class TestComplaintEvidences:
    """Tests for GET /api/fichas/{ficha}/complaint-evidences."""

    def test_returns_evidences(self, client):
        res = client.get("/api/fichas/3388997/complaint-evidences")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 3
        assert data[0]["item_id"] == 1001
        assert data[0]["name"] == "AA1-EV01 Informe"
        assert data[0]["category"] == "Fase 1 Analisis"

    def test_returns_grade_counts(self, client):
        res = client.get("/api/fichas/3388997/complaint-evidences")
        data = res.json()
        # Evidence 1001: JUAN=-, MARIA=A, PEDRO=A → 2 approved, 1 pending
        ev1 = next(e for e in data if e["item_id"] == 1001)
        assert ev1["total_approved"] == 2
        assert ev1["total_pending"] == 1

    def test_sin_nombre_del_instructor_no_genera(self, client):
        res = client.post("/api/fichas/3388997/complaint-reports/generate", json={
            "user_ids": [100],
            "evidence_ids": [1001],
        })
        assert res.status_code == 422

    def test_404_for_unknown_ficha(self, client):
        res = client.get("/api/fichas/9999999/complaint-evidences")
        assert res.status_code == 404


class TestComplaintCandidates:
    """Tests for POST /api/fichas/{ficha}/complaint-candidates."""

    def test_filters_by_inactivity_and_pending(self, client):
        res = client.post("/api/fichas/3388997/complaint-candidates", json={
            "evidence_ids": [1001, 1002, 1003],
            "min_days_inactive": 20,
        })
        assert res.status_code == 200
        data = res.json()
        # JUAN: 25 days inactive, all 3 pending → candidate
        # MARIA: 5 days inactive → excluded (not enough days)
        # PEDRO: 30 days inactive but all approved → excluded (no pending)
        assert data["total"] == 1
        assert data["candidates"][0]["user_id"] == 100
        assert data["candidates"][0]["full_name"] == "JUAN PEREZ"
        assert data["candidates"][0]["pending_count"] == 3

    def test_filters_specific_evidences(self, client):
        res = client.post("/api/fichas/3388997/complaint-candidates", json={
            "evidence_ids": [1002],  # Only check evidence 1002
            "min_days_inactive": 20,
        })
        data = res.json()
        # JUAN: 25 days, 1002 pending → candidate
        # PEDRO: 30 days, 1002 approved → excluded
        assert data["total"] == 1
        assert data["candidates"][0]["pending_count"] == 1
        assert data["candidates"][0]["total_selected"] == 1

    def test_no_candidates_when_low_inactivity(self, client):
        res = client.post("/api/fichas/3388997/complaint-candidates", json={
            "evidence_ids": [1001, 1002, 1003],
            "min_days_inactive": 50,
        })
        data = res.json()
        assert data["total"] == 0

    def test_pending_evidences_detail(self, client):
        res = client.post("/api/fichas/3388997/complaint-candidates", json={
            "evidence_ids": [1001, 1002],
            "min_days_inactive": 20,
        })
        data = res.json()
        candidate = data["candidates"][0]
        pending_names = [e["name"] for e in candidate["pending_evidences"]]
        assert "AA1-EV01 Informe" in pending_names
        assert "AA1-EV02 Taller" in pending_names

    def test_sin_nombre_del_instructor_no_genera(self, client):
        res = client.post("/api/fichas/3388997/complaint-reports/generate", json={
            "user_ids": [100],
            "evidence_ids": [1001],
        })
        assert res.status_code == 422

    def test_404_for_unknown_ficha(self, client):
        res = client.post("/api/fichas/9999999/complaint-candidates", json={
            "evidence_ids": [1001],
        })
        assert res.status_code == 404


class TestComplaintGenerate:
    """Tests for POST /api/fichas/{ficha}/complaint-reports/generate."""

    def test_generates_zip(self, client):
        with patch("docx2pdf.convert", side_effect=_fake_docx2pdf_convert):
            res = client.post("/api/fichas/3388997/complaint-reports/generate", json={
                "user_ids": [100],
                "instructor_name": "INSTRUCTOR TEST",
                "evidence_ids": [1001, 1002, 1003],
                "coordinator_name": "COORDINADOR TEST",
            })
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/zip"

        # Verify ZIP contents
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        names = zf.namelist()
        docx_files = [n for n in names if n.startswith("Word/") and n.endswith(".docx")]
        pdf_files = [n for n in names if n.startswith("PDF/") and n.endswith(".pdf")]
        assert len(docx_files) == 1
        assert len(pdf_files) == 1
        assert "_1234567890" in docx_files[0]

    def test_generates_multiple_reports(self, client):
        # Make PEDRO also have a pending evidence for this test
        snapshot = dict(MOCK_SNAPSHOT)
        courses = [dict(c) for c in snapshot["courses"]]
        students = [dict(s) for s in courses[0]["students"]]
        # Give PEDRO a pending grade on 1001
        pedro = dict(students[2])
        pedro["grades"] = dict(pedro["grades"])
        pedro["grades"]["1001"] = {"evidence_id": 1001, "value": "-", "passed": False}
        students[2] = pedro
        courses[0] = {**courses[0], "students": students}
        snapshot["courses"] = courses

        app.dependency_overrides[get_snapshot] = lambda: snapshot

        with patch("docx2pdf.convert", side_effect=_fake_docx2pdf_convert):
            res = client.post("/api/fichas/3388997/complaint-reports/generate", json={
                "user_ids": [100, 102],
                "instructor_name": "INSTRUCTOR TEST",
                "evidence_ids": [1001, 1002, 1003],
            })
        assert res.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        docx_files = [n for n in zf.namelist() if n.startswith("Word/")]
        pdf_files = [n for n in zf.namelist() if n.startswith("PDF/")]
        assert len(docx_files) == 2
        assert len(pdf_files) == 2

    def test_empty_user_ids_returns_400(self, client):
        res = client.post("/api/fichas/3388997/complaint-reports/generate", json={
            "user_ids": [],
            "instructor_name": "INSTRUCTOR TEST",
            "evidence_ids": [1001],
        })
        assert res.status_code == 400

    def test_no_pending_returns_400(self, client):
        # PEDRO has no pending evidences → should not generate
        res = client.post("/api/fichas/3388997/complaint-reports/generate", json={
            "user_ids": [102],
            "instructor_name": "INSTRUCTOR TEST",
            "evidence_ids": [1001, 1002, 1003],
        })
        assert res.status_code == 400

    def test_sin_nombre_del_instructor_no_genera(self, client):
        res = client.post("/api/fichas/3388997/complaint-reports/generate", json={
            "user_ids": [100],
            "evidence_ids": [1001],
        })
        assert res.status_code == 422

    def test_404_for_unknown_ficha(self, client):
        res = client.post("/api/fichas/9999999/complaint-reports/generate", json={
            "user_ids": [100],
            "instructor_name": "INSTRUCTOR TEST",
            "evidence_ids": [1001],
        })
        assert res.status_code == 404
