"""Tests for the report engine and API endpoint."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.report_engine import generate_report
from src.api.server import app

# --- Mock data ---

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
                        "1001": {"evidence_id": 1001, "value": "A", "passed": True},
                        "1002": {"evidence_id": 1002, "value": "D", "passed": False},
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
                        "1002": {"evidence_id": 1002, "value": "-", "passed": False},
                        "1003": {"evidence_id": 1003, "value": "-", "passed": False},
                    },
                },
                {
                    "user_id": 102,
                    "full_name": "PEDRO MARTINEZ",
                    "document": "5555555555",
                    "email": "pedro@test.com",
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
                {
                    "user_id": 102,
                    "full_name": "PEDRO MARTINEZ",
                    "document": "5555555555",
                    "email": "pedro@test.com",
                    "role": "Aprendiz",
                    "groups": "Grupo A",
                    "last_access_raw": "2 horas",
                    "last_access_days": 0,
                    "status": "Activo",
                },
            ],
        },
    ],
    "errors": [],
}


# --- Report engine unit tests ---

@pytest.fixture(autouse=True)
def _no_submission_status():
    """By default, no yellow cells."""
    with patch("src.api.report_engine._load_submission_status", return_value=set()):
        yield


class TestReportEngine:
    def test_basic_report(self):
        result = generate_report(MOCK_SNAPSHOT, "3388997", [1001, 1002, 1003])
        assert result["ficha"] == "3388997"
        assert result["selected_evidences_count"] == 3
        # PEDRO has all approved, so only JUAN and MARIA have overdue
        assert result["total_students_with_overdue"] == 2
        # All 3 students are returned
        assert result["total_students"] == 3

    def test_only_pending_counted(self):
        result = generate_report(MOCK_SNAPSHOT, "3388997", [1001])
        # Only MARIA has 1001 pending; JUAN has A, PEDRO has A
        assert result["total_students_with_overdue"] == 1
        assert result["total_students"] == 3
        # First student has overdue (sorted desc by overdue_count)
        assert result["students"][0]["full_name"] == "MARIA GOMEZ"
        assert result["students"][0]["overdue_count"] == 1

    def test_student_sorted_by_overdue_count(self):
        result = generate_report(MOCK_SNAPSHOT, "3388997", [1001, 1002, 1003])
        # MARIA has 3 pending, JUAN has 2 (D on 1002, "-" on 1003)
        assert result["students"][0]["full_name"] == "MARIA GOMEZ"
        assert result["students"][0]["overdue_count"] == 3
        assert result["students"][1]["full_name"] == "JUAN PEREZ"
        assert result["students"][1]["overdue_count"] == 2

    def test_overdue_evidence_details(self):
        result = generate_report(MOCK_SNAPSHOT, "3388997", [1003])
        maria = next(s for s in result["students"] if s["full_name"] == "MARIA GOMEZ")
        assert len(maria["overdue_evidences"]) == 1
        assert maria["overdue_evidences"][0]["item_id"] == 1003
        assert maria["overdue_evidences"][0]["name"] == "AA2-EV01 Proyecto"
        assert maria["overdue_evidences"][0]["category"] == "Fase 2"

    def test_includes_participant_data(self):
        result = generate_report(MOCK_SNAPSHOT, "3388997", [1001, 1002, 1003])
        maria = next(s for s in result["students"] if s["full_name"] == "MARIA GOMEZ")
        assert maria["status"] == "Suspendido"
        assert maria["last_access_days"] == 47
        assert maria["email"] == "maria@test.com"

    def test_all_approved_has_zero_overdue(self):
        # PEDRO has A on all → appears with overdue_count=0
        result = generate_report(MOCK_SNAPSHOT, "3388997", [1001])
        pedro = next(s for s in result["students"] if s["full_name"] == "PEDRO MARTINEZ")
        assert pedro["overdue_count"] == 0

    def test_nonexistent_ficha(self):
        result = generate_report(MOCK_SNAPSHOT, "9999999", [1001])
        assert result["total_students_with_overdue"] == 0
        assert result["total_students"] == 0
        assert result["students"] == []

    def test_disapproved_counted_as_overdue(self):
        # JUAN has D on 1002 - disapproved IS overdue (student needs to redo)
        result = generate_report(MOCK_SNAPSHOT, "3388997", [1002])
        juan_found = any(s["full_name"] == "JUAN PEREZ" for s in result["students"])
        assert juan_found  # D means student needs to redo

    def test_empty_evidence_ids_returns_empty(self):
        result = generate_report(MOCK_SNAPSHOT, "3388997", [])
        assert result["total_students_with_overdue"] == 0


class TestReportYellowCellExclusion:
    """Tests for excluding yellow cells (submitted but ungraded) from reports."""

    def test_yellow_cell_excluded(self):
        """If a student's pending evidence is yellow, exclude it from overdue."""
        with patch(
            "src.api.report_engine._load_submission_status",
            return_value={"1001:101"},  # MARIA's 1001 is yellow
        ):
            result = generate_report(MOCK_SNAPSHOT, "3388997", [1001])
            # MARIA's only selected evidence (1001) is yellow → excluded entirely
            assert result["total_students_with_overdue"] == 0

    def test_mixed_yellow_and_pending(self):
        """Student with some yellow and some truly pending evidences."""
        with patch(
            "src.api.report_engine._load_submission_status",
            return_value={"1001:101"},  # MARIA's 1001 is yellow
        ):
            result = generate_report(MOCK_SNAPSHOT, "3388997", [1001, 1002, 1003])
            maria = next(s for s in result["students"] if s["full_name"] == "MARIA GOMEZ")
            # 1001 yellow → excluded, 1002 and 1003 still pending
            assert maria["overdue_count"] == 2
            ev_ids = [e["item_id"] for e in maria["overdue_evidences"]]
            assert 1001 not in ev_ids
            assert 1002 in ev_ids
            assert 1003 in ev_ids

    def test_all_yellow_student_has_zero_overdue(self):
        """If ALL of a student's pending evidences are yellow, overdue_count=0."""
        with patch(
            "src.api.report_engine._load_submission_status",
            return_value={"1001:101", "1002:101", "1003:101"},
        ):
            result = generate_report(MOCK_SNAPSHOT, "3388997", [1001, 1002, 1003])
            maria = next(s for s in result["students"] if s["full_name"] == "MARIA GOMEZ")
            assert maria["overdue_count"] == 0

    def test_yellow_does_not_affect_other_students(self):
        """Yellow cell for one student shouldn't affect another."""
        with patch(
            "src.api.report_engine._load_submission_status",
            return_value={"1001:101"},  # Only MARIA's 1001 is yellow
        ):
            result = generate_report(MOCK_SNAPSHOT, "3388997", [1003])
            # JUAN still has 1003 pending, MARIA still has 1003 pending
            assert result["total_students_with_overdue"] == 2


# --- API tests ---

@pytest.fixture
def client():
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    with (
        patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        patch("src.api.report_engine._load_submission_status", return_value=set()),
        TestClient(app) as c,
    ):
        yield c
    app.dependency_overrides.clear()


class TestReportsAPI:
    def test_post_report(self, client):
        resp = client.post(
            "/api/reports/3388997",
            json={"evidence_ids": [1001, 1002, 1003]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ficha"] == "3388997"
        assert data["selected_evidences_count"] == 3
        assert data["total_students_with_overdue"] == 2
        assert data["total_students"] == 3
        assert len(data["students"]) == 3  # Includes al-dia students

    def test_report_student_fields(self, client):
        resp = client.post(
            "/api/reports/3388997",
            json={"evidence_ids": [1001, 1002, 1003]},
        )
        student = resp.json()["students"][0]
        assert "user_id" in student
        assert "full_name" in student
        assert "document" in student
        assert "email" in student
        assert "status" in student
        assert "last_access_days" in student
        assert "overdue_evidences" in student
        assert "overdue_count" in student

    def test_report_overdue_evidence_fields(self, client):
        resp = client.post(
            "/api/reports/3388997",
            json={"evidence_ids": [1003]},
        )
        ev = resp.json()["students"][0]["overdue_evidences"][0]
        assert "item_id" in ev
        assert "name" in ev
        assert "category" in ev

    def test_report_ficha_not_found(self, client):
        resp = client.post(
            "/api/reports/9999999",
            json={"evidence_ids": [1001]},
        )
        assert resp.status_code == 404

    def test_report_empty_evidence_ids(self, client):
        resp = client.post(
            "/api/reports/3388997",
            json={"evidence_ids": []},
        )
        assert resp.status_code == 400

    def test_report_single_evidence(self, client):
        resp = client.post(
            "/api/reports/3388997",
            json={"evidence_ids": [1003]},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 1003 is pending for JUAN and MARIA
        assert data["total_students_with_overdue"] == 2
        assert data["total_students"] == 3  # All students returned
