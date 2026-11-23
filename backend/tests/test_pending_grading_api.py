"""Tests for pending grading API endpoints (assignments + forums)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_base_config, get_config, get_snapshot
from src.api.routes import pending_grading
from src.api.server import app
from src.client.zajuna import FetchError

FIXTURES = Path(__file__).parent / "fixtures"

MOCK_SNAPSHOT = {
    "timestamp": "2026-03-01T05:00:12",
    "courses": [
        {
            "course_id": 89977,
            "ficha": "3388997",
            "course_name": "ADSO",
            "evidences": [
                {"item_id": 100, "name": "GA1-220501092-AA1-EV01 Infografia", "category": "ANALISIS"},
                {"item_id": 101, "name": "GA1-220501092-AA1-EV02 Taller", "category": "ANALISIS"},
            ],
            "students": [],
        },
    ],
    "summaries": [],
    "participants": [],
    "errors": [],
}

MOCK_ASSIGNMENTS = {
    "ficha": "3388997",
    "course_id": 89977,
    "updated_at": "2026-03-05T10:30:00",
    "assignments": [
        {"name": "GA1-220501092-AA1-EV01 Infografia", "cmid": 1343194, "item_id": 100, "module_type": "assign"},
        {"name": "GA1-220501092-AA1-EV02 Taller", "cmid": 1343195, "item_id": 101, "module_type": "assign"},
        {"name": "Foro de participacion", "cmid": 565694, "item_id": 200, "module_type": "forum"},
        {"name": "Foro sin item_id", "cmid": 565695, "item_id": None, "module_type": "forum"},
        {"name": "Cuestionario. GA1-240202501-AA1-EV01.", "cmid": 1500001, "item_id": 300, "module_type": "quiz"},
    ],
}


@pytest.fixture(autouse=True)
def _fresh_zajuna_session():
    """Cada prueba arma su propio cliente simulado: sin sesión compartida previa."""
    pending_grading._sessions.clear()
    yield
    pending_grading._sessions.clear()


@pytest.fixture
def client(tmp_path):
    """TestClient with mocked snapshot and temp assignments store."""
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    # Zajuna va mockeado: basta la config del .env, sin cuenta del vault.
    app.dependency_overrides[get_config] = get_base_config
    with (
        patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT),
        patch("src.store.assignments_store.ASSIGNMENTS_DIR", tmp_path / "assignments"),
        TestClient(app) as c,
    ):
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_assignments(tmp_path):
    """TestClient with pre-loaded assignment mapping."""
    app.dependency_overrides[get_snapshot] = lambda: MOCK_SNAPSHOT
    # Zajuna va mockeado: basta la config del .env, sin cuenta del vault.
    app.dependency_overrides[get_config] = get_base_config
    assignments_dir = tmp_path / "assignments"
    with patch("src.api.dependencies.load_snapshot", return_value=MOCK_SNAPSHOT), \
         patch("src.store.assignments_store.ASSIGNMENTS_DIR", assignments_dir), \
         patch(
             "src.api.routes.pending_grading.load_assignments",
             return_value=MOCK_ASSIGNMENTS,
         ), TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ─── GET /assignments ────────────────────────────────────────────────────


class TestGetAssignments:
    def test_returns_404_when_no_mapping(self, client):
        r = client.get("/api/fichas/3388997/assignments")
        assert r.status_code == 404

    def test_returns_mapping_when_exists(self, client_with_assignments):
        r = client_with_assignments.get("/api/fichas/3388997/assignments")
        assert r.status_code == 200
        data = r.json()
        assert data["ficha"] == "3388997"
        assert data["course_id"] == 89977
        assert len(data["assignments"]) == 5

    def test_assignment_fields(self, client_with_assignments):
        r = client_with_assignments.get("/api/fichas/3388997/assignments")
        data = r.json()
        first = data["assignments"][0]
        assert first["name"] == "GA1-220501092-AA1-EV01 Infografia"
        assert first["cmid"] == 1343194
        assert first["item_id"] == 100
        assert first["module_type"] == "assign"

    def test_forum_module_type(self, client_with_assignments):
        r = client_with_assignments.get("/api/fichas/3388997/assignments")
        data = r.json()
        forum = data["assignments"][2]
        assert forum["module_type"] == "forum"
        assert forum["cmid"] == 565694

    def test_unmatched_assignment_has_null_item_id(self, client_with_assignments):
        r = client_with_assignments.get("/api/fichas/3388997/assignments")
        data = r.json()
        last = data["assignments"][3]
        assert last["name"] == "Foro sin item_id"
        assert last["item_id"] is None

    def test_has_updated_at(self, client_with_assignments):
        r = client_with_assignments.get("/api/fichas/3388997/assignments")
        data = r.json()
        assert "updated_at" in data
        assert data["updated_at"] == "2026-03-05T10:30:00"


# ─── POST /pending-grading (assignments) ─────────────────────────────────


class TestCheckAssignmentPending:
    def test_returns_404_when_no_mapping(self, client):
        r = client.post(
            "/api/fichas/3388997/pending-grading",
            json={"item_ids": [100]},
        )
        assert r.status_code == 404

    def test_unknown_item_id_returns_error(self, client_with_assignments):
        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient"):
            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [999]},
            )
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["item_id"] == 999
        assert data["results"][0]["error"] is not None

    def test_successful_check(self, client_with_assignments):
        mock_html = """
        <html><body>
        <table class="generaltable">
            <tr><td>Participantes</td><td>44</td></tr>
            <tr><td>Borradores</td><td>0</td></tr>
            <tr><td>Enviados</td><td>35</td></tr>
            <tr><td>Pendientes por calificar</td><td>12</td></tr>
        </table>
        </body></html>
        """
        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_assignment_detail.return_value = mock_html
            mock_client.fetch_submissions_list.return_value = "<html></html>"

            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [100]},
            )

        assert r.status_code == 200
        data = r.json()
        result = data["results"][0]
        assert result["item_id"] == 100
        assert result["cmid"] == 1343194
        assert result["module_type"] == "assign"
        assert result["participants"] == 44
        assert result["submitted"] == 35
        assert result["needs_grading"] == 12

    def test_lists_pending_students_when_something_is_pending(self, client_with_assignments):
        """Only 'Enviado para calificar' and not graded counts as waiting."""
        detail_html = """
        <table class="generaltable">
            <tr><td>Participantes</td><td>6</td></tr>
            <tr><td>Enviados</td><td>4</td></tr>
            <tr><td>Pendientes por calificar</td><td>1</td></tr>
        </table>
        """
        submissions_html = (FIXTURES / "assignment_submissions_sample.html").read_text(
            encoding="utf-8"
        )
        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_assignment_detail.return_value = detail_html
            mock_client.fetch_submissions_list.return_value = submissions_html

            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [100]},
            )

        assert r.status_code == 200
        pending = r.json()["results"][0]["pending_students"]
        assert [s["user_id"] for s in pending] == [900100]
        assert pending[0]["file_count"] == 1
        assert pending[0]["last_modified"] is not None

    def test_skips_student_list_when_nothing_is_pending(self, client_with_assignments):
        detail_html = """
        <table class="generaltable">
            <tr><td>Participantes</td><td>6</td></tr>
            <tr><td>Enviados</td><td>3</td></tr>
            <tr><td>Pendientes por calificar</td><td>0</td></tr>
        </table>
        """
        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_assignment_detail.return_value = detail_html

            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [100]},
            )
            mock_client.fetch_submissions_list.assert_not_called()

        assert r.json()["results"][0]["pending_students"] == []

    def test_multiple_items(self, client_with_assignments):
        mock_html = """
        <html><body>
        <table class="generaltable">
            <tr><td>Participantes</td><td>44</td></tr>
            <tr><td>Borradores</td><td>1</td></tr>
            <tr><td>Enviados</td><td>30</td></tr>
            <tr><td>Pendientes por calificar</td><td>5</td></tr>
        </table>
        </body></html>
        """
        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_assignment_detail.return_value = mock_html
            mock_client.fetch_submissions_list.return_value = "<html></html>"

            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [100, 101]},
            )

        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 2
        assert all(r["needs_grading"] == 5 for r in data["results"])

    def test_has_checked_at(self, client_with_assignments):
        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient"):
            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [999]},
            )
        data = r.json()
        assert "checked_at" in data


# ─── POST /pending-grading (forums) ──────────────────────────────────────


class TestCheckForumPending:
    def test_forum_check_successful(self, client_with_assignments):
        """Forum check: view page → 2 discussions → count ungraded."""
        forum_view_html = """
        <table class="discussion-list generaltable">
            <tr class="discussion" data-discussionid="5001">
                <th class="topic"><a class="w-100">Discussion 1</a></th>
            </tr>
            <tr class="discussion" data-discussionid="5002">
                <th class="topic"><a class="w-100">Discussion 2</a></th>
            </tr>
        </table>
        """
        disc1_html = """
        <form class="postratingform"><span class="ratingaggregate">100</span></form>
        <form class="postratingform"><span class="ratingaggregate"></span></form>
        """
        disc2_html = """
        <form class="postratingform"><span class="ratingaggregate"></span></form>
        """

        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_forum_view.return_value = forum_view_html
            mock_client.fetch_forum_discussion.side_effect = [disc1_html, disc2_html]

            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [200]},
            )

        assert r.status_code == 200
        data = r.json()
        result = data["results"][0]
        assert result["item_id"] == 200
        assert result["module_type"] == "forum"
        assert result["total_discussions"] == 2
        assert result["participants"] == 3      # Total posts with rating forms
        assert result["submitted"] == 1         # Graded posts
        assert result["needs_grading"] == 2     # Ungraded posts
        assert result["error"] is None

    def test_forum_empty_discussions(self, client_with_assignments):
        """Forum with no discussions."""
        empty_html = "<table class='discussion-list'></table>"

        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_forum_view.return_value = empty_html

            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [200]},
            )

        # Should return error because no discussions found
        result = r.json()["results"][0]
        assert result["error"] is not None

    def test_forum_all_graded(self, client_with_assignments):
        """Forum where all posts are graded."""
        forum_view_html = """
        <table class="discussion-list generaltable">
            <tr class="discussion" data-discussionid="5001">
                <th class="topic"><a class="w-100">Test</a></th>
            </tr>
        </table>
        """
        disc_html = """
        <form class="postratingform"><span class="ratingaggregate">100</span></form>
        <form class="postratingform"><span class="ratingaggregate">80</span></form>
        """

        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_forum_view.return_value = forum_view_html
            mock_client.fetch_forum_discussion.return_value = disc_html

            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [200]},
            )

        result = r.json()["results"][0]
        assert result["needs_grading"] == 0
        assert result["submitted"] == 2


# ─── POST /pending-grading (quizzes) ─────────────────────────────────────


class TestCheckQuizPending:
    def test_quiz_returns_auto_graded_immediately(self, client_with_assignments):
        """Quiz should return immediately with needs_grading=0, no Zajuna scraping."""
        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value

            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [300]},
            )

            # Should NOT call any fetch methods for quizzes
            mock_client.fetch_assignment_detail.assert_not_called()
            mock_client.fetch_forum_view.assert_not_called()

        assert r.status_code == 200
        data = r.json()
        result = data["results"][0]
        assert result["item_id"] == 300
        assert result["cmid"] == 1500001
        assert result["module_type"] == "quiz"
        assert result["needs_grading"] == 0
        assert result["error"] is None

    def test_quiz_mixed_with_assignment(self, client_with_assignments):
        """Quiz + assignment in same request: quiz returns instantly, assignment is fetched."""
        mock_html = """
        <html><body>
        <table class="generaltable">
            <tr><td>Participantes</td><td>44</td></tr>
            <tr><td>Borradores</td><td>0</td></tr>
            <tr><td>Enviados</td><td>30</td></tr>
            <tr><td>Pendientes por calificar</td><td>3</td></tr>
        </table>
        </body></html>
        """
        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_assignment_detail.return_value = mock_html
            mock_client.fetch_submissions_list.return_value = "<html></html>"

            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [300, 100]},
            )

        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 2

        quiz_result = next(r for r in data["results"] if r["item_id"] == 300)
        assign_result = next(r for r in data["results"] if r["item_id"] == 100)

        assert quiz_result["module_type"] == "quiz"
        assert quiz_result["needs_grading"] == 0

        assert assign_result["module_type"] == "assign"
        assert assign_result["needs_grading"] == 3

    def test_quiz_module_type_in_get_assignments(self, client_with_assignments):
        """GET /assignments should include quiz module_type."""
        r = client_with_assignments.get("/api/fichas/3388997/assignments")
        data = r.json()
        quiz = next(a for a in data["assignments"] if a["module_type"] == "quiz")
        assert quiz["name"] == "Cuestionario. GA1-240202501-AA1-EV01."
        assert quiz["cmid"] == 1500001
        assert quiz["item_id"] == 300

    def test_quiz_counts_come_from_instructor_snapshot(self, client_with_assignments):
        """Regresión: los conteos A/D/- del quiz se leen del snapshot inyectado.

        Antes se llamaba get_snapshot() sin request; el TypeError se tragaba
        y los conteos salían siempre (0, 0, 0).
        """
        graded = {
            **MOCK_SNAPSHOT,
            "courses": [{
                **MOCK_SNAPSHOT["courses"][0],
                "students": [
                    {"grades": {"300": {"value": "A"}}},
                    {"grades": {"300": {"value": "A"}}},
                    {"grades": {"300": {"value": "D"}}},
                    {"grades": {"300": {"value": "-"}}},
                    {"grades": {}},
                ],
            }],
        }
        app.dependency_overrides[get_snapshot] = lambda: graded
        with patch("src.api.routes.pending_grading.AuthManager"), \
             patch("src.api.routes.pending_grading.ZajunaClient"):
            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [300]},
            )

        assert r.status_code == 200
        result = r.json()["results"][0]
        assert result["quiz_approved"] == 2
        assert result["quiz_disapproved"] == 1
        assert result["quiz_pending"] == 2
        assert result["participants"] == 5
        assert result["submitted"] == 3


# ─── Sesión compartida y fallos por fila ─────────────────────────────────

FORUM_TWO_DISCUSSIONS = """
<table class="discussion-list generaltable">
    <tr class="discussion" data-discussionid="5001">
        <th class="topic"><a class="w-100">Discussion 1</a></th>
    </tr>
    <tr class="discussion" data-discussionid="5002">
        <th class="topic"><a class="w-100">Discussion 2</a></th>
    </tr>
</table>
"""
UNGRADED_POST = '<form class="postratingform"><span class="ratingaggregate"></span></form>'
DETAIL_ZERO = """
<table class="generaltable">
    <tr><td>Participantes</td><td>6</td></tr>
    <tr><td>Enviados</td><td>3</td></tr>
    <tr><td>Pendientes por calificar</td><td>0</td></tr>
</table>
"""


class TestSharedSessionAndRowErrors:
    def test_reuses_one_login_across_requests(self, client_with_assignments):
        """El frontend pide una evidencia por petición: un solo login para todas."""
        with patch("src.api.routes.pending_grading.AuthManager") as MockAuth,              patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            MockClient.return_value.fetch_assignment_detail.return_value = DETAIL_ZERO
            for item_id in (100, 101, 100):
                r = client_with_assignments.post(
                    "/api/fichas/3388997/pending-grading",
                    json={"item_ids": [item_id]},
                )
                assert r.status_code == 200
        assert MockAuth.return_value.login.call_count == 1

    def test_quiz_only_does_not_log_in(self, client_with_assignments):
        with patch("src.api.routes.pending_grading.AuthManager") as MockAuth,              patch("src.api.routes.pending_grading.ZajunaClient"):
            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [300]},
            )
        assert r.status_code == 200
        assert r.json()["results"][0]["error"] is None
        MockAuth.return_value.login.assert_not_called()

    def test_failed_login_is_503_and_not_cached(self, client_with_assignments):
        with patch("src.api.routes.pending_grading.AuthManager") as MockAuth,              patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            MockAuth.return_value.login.side_effect = [RuntimeError("caída"), None]
            MockClient.return_value.fetch_assignment_detail.return_value = DETAIL_ZERO
            r1 = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading", json={"item_ids": [100]},
            )
            r2 = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading", json={"item_ids": [100]},
            )
        assert r1.status_code == 503
        assert "No se pudo iniciar sesión en Zajuna" in r1.json()["detail"]
        assert r2.status_code == 200

    def test_unexpected_error_stays_in_its_row(self, client_with_assignments):
        """Antes un error no previsto daba 500 sin CORS: el navegador solo
        decía "Failed to fetch" y se perdían las demás filas."""
        with patch("src.api.routes.pending_grading.AuthManager"),              patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_forum_view.side_effect = RuntimeError("algo raro")
            mock_client.fetch_assignment_detail.return_value = DETAIL_ZERO
            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading",
                json={"item_ids": [200, 100]},
            )
        assert r.status_code == 200
        forum, assign = r.json()["results"]
        assert "algo raro" in forum["error"]
        assert assign["error"] is None

    def test_forum_retries_a_discussion_that_failed_once(self, client_with_assignments):
        with patch("src.api.routes.pending_grading.AuthManager"),              patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_forum_view.return_value = FORUM_TWO_DISCUSSIONS
            mock_client.fetch_forum_discussion.side_effect = [
                UNGRADED_POST, FetchError("corte"), UNGRADED_POST,
            ]
            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading", json={"item_ids": [200]},
            )
        result = r.json()["results"][0]
        assert result["error"] is None
        assert result["needs_grading"] == 2

    def test_forum_with_a_discussion_still_failing_reports_error(self, client_with_assignments):
        """Contar solo parte del foro daría un "por calificar" falso."""
        with patch("src.api.routes.pending_grading.AuthManager"),              patch("src.api.routes.pending_grading.ZajunaClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.fetch_forum_view.return_value = FORUM_TWO_DISCUSSIONS
            mock_client.fetch_forum_discussion.side_effect = [
                UNGRADED_POST, FetchError("corte"), FetchError("corte otra vez"),
            ]
            r = client_with_assignments.post(
                "/api/fichas/3388997/pending-grading", json={"item_ids": [200]},
            )
        result = r.json()["results"][0]
        assert "1 de 2 hilos" in result["error"]
        assert result["needs_grading"] is None
