"""Foros, fase 1: aportes que esperan réplica del instructor (SAVA 9.1.6)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.api.alerts import forum_reply_alerts
from src.api.dependencies import get_base_config, get_config, get_snapshot
from src.api.forum_inbox import apprentice_ids, build_contributions, contribution_status
from src.api.server import app
from src.client.zajuna import FetchError
from src.parsers.forum_posts import ForumPost, parse_forum_posts
from src.store.instructor_scope import as_instructor
from src.utils.business_days import (
    business_days_between,
    colombian_holidays,
    is_business_day,
    next_business_day,
)

FIXTURES = Path(__file__).parent / "fixtures"
THREADED = (FIXTURES / "forum_discussion_threaded.html").read_text(encoding="utf-8")
FLAT = (FIXTURES / "forum_discussion_sample.html").read_text(encoding="utf-8")
VIEW = (FIXTURES / "forum_view_sample.html").read_text(encoding="utf-8")

APPRENTICES = {9000001, 9000002, 9000003}
COL = timezone(timedelta(hours=-5))


# ─── Días hábiles ───────────────────────────────────────────────────────────


class TestBusinessDays:
    def test_festivos_2026(self):
        expected = {
            date(2026, 1, 1), date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2),
            date(2026, 4, 3), date(2026, 5, 1), date(2026, 5, 18), date(2026, 6, 8),
            date(2026, 6, 15), date(2026, 6, 29), date(2026, 7, 20), date(2026, 8, 7),
            date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 16),
            date(2026, 12, 8), date(2026, 12, 25),
        }
        assert colombian_holidays(2026) == expected

    def test_pascua_de_2027(self):
        # Pascua 2027: 28 de marzo → Jueves Santo 25, Ascensión lunes 10 de mayo
        holidays = colombian_holidays(2027)
        assert date(2027, 3, 25) in holidays
        assert date(2027, 5, 10) in holidays

    def test_fin_de_semana_y_festivo_no_son_habiles(self):
        assert not is_business_day(date(2026, 10, 31))  # sábado
        assert not is_business_day(date(2026, 11, 2))  # festivo
        assert is_business_day(date(2026, 11, 3))

    def test_viernes_antes_de_puente_vence_el_martes(self):
        assert next_business_day(date(2026, 10, 30)) == date(2026, 11, 3)

    def test_dias_habiles_transcurridos(self):
        assert business_days_between(date(2026, 10, 30), date(2026, 11, 4)) == 2
        assert business_days_between(date(2026, 11, 4), date(2026, 11, 4)) == 0


# ─── Parser ─────────────────────────────────────────────────────────────────


class TestForumPostsParser:
    def test_anidado_respeta_el_padre(self):
        posts = {p.post_id: p for p in parse_forum_posts(THREADED, 600001)}
        assert set(posts) == {700001, 700002, 700003, 700004}
        assert posts[700001].parent_id is None
        assert posts[700002].parent_id == 700001
        assert posts[700003].parent_id == 700001
        assert posts[700004].parent_id == 700002

    def test_autor_fecha_y_texto(self):
        first = parse_forum_posts(THREADED, 600001)[0]
        assert first.author_name == "ANA PRUEBA UNO"
        assert first.author_user_id == 9000001
        assert first.created_at == datetime(2026, 10, 30, 15, 23, 54, tzinfo=COL)
        assert first.discussion_id == 600001
        # Texto limpio: sin etiquetas ni espacios repetidos, y sin el de las respuestas
        assert "Entrevistas: permiten conocer las necesidades del cliente" in first.text
        assert "documentos del negocio" in first.text
        assert "compañera" not in first.text

    def test_calificacion(self):
        posts = {p.post_id: p for p in parse_forum_posts(THREADED, 600001)}
        rating = posts[700001].rating
        assert rating is not None
        assert rating.aggregate == "100"
        assert rating.item_id == 700001
        assert rating.scale_id == 100
        assert rating.context_id == 555001
        assert [v for v, _ in rating.options] == ["0", "50", "100"]
        assert posts[700002].rating.aggregate is None
        # El instructor no tiene formulario propio (no se toma el de otra publicación)
        assert posts[700004].rating is None

    def test_no_guarda_el_sesskey(self):
        for post in parse_forum_posts(THREADED, 600001):
            assert "FALSOFALSO" not in repr(post)

    def test_discusion_plana(self):
        posts = parse_forum_posts(FLAT, 5545198)
        assert len(posts) == 3
        assert all(p.parent_id is None for p in posts)
        assert posts[1].rating.aggregate is None


# ─── Reglas de la bandeja ───────────────────────────────────────────────────


def _post(post_id, parent, author, when, discussion=1):
    return ForumPost(
        post_id=post_id, discussion_id=discussion, parent_id=parent, subject="",
        author_name=f"Autor {author}", author_user_id=author,
        created_at=datetime.fromisoformat(when), text="texto", rating=None,
    )


class TestForumInbox:
    def test_respuestas_entre_companeros_no_son_aportes(self):
        contributions, peers = build_contributions(
            parse_forum_posts(THREADED, 600001), APPRENTICES, "Fuentes"
        )
        assert [c["post_id"] for c in contributions] == [700001]
        assert peers == 2
        # La réplica del instructor está dos niveles abajo: igual cuenta
        assert contributions[0]["first_reply_at"] == "2026-11-03T08:05:00-05:00"
        assert contributions[0]["grade"] == "100"
        assert contributions[0]["discussion_title"] == "Fuentes"

    def test_respondido_dentro_del_plazo(self):
        contributions, _ = build_contributions(
            parse_forum_posts(THREADED, 600001), APPRENTICES, "Fuentes"
        )
        status = contribution_status(contributions[0], date(2026, 11, 20))
        assert status == {"reply_due": "2026-11-03", "status": "respondido", "business_days_waiting": 0}

    def test_sin_instructor_vence(self):
        # Sin la réplica del instructor (8000001 pasa a ser aprendiz)
        contributions, _ = build_contributions(
            parse_forum_posts(THREADED, 600001), APPRENTICES | {8000001}, "Fuentes"
        )
        item = contributions[0]
        assert item["first_reply_at"] is None
        assert contribution_status(item, date(2026, 11, 2))["status"] == "a_tiempo"
        assert contribution_status(item, date(2026, 11, 3))["status"] == "vence_hoy"
        late = contribution_status(item, date(2026, 11, 4))
        assert late["status"] == "vencido"
        assert late["business_days_waiting"] == 2

    def test_respondido_tarde(self):
        posts = [
            _post(1, None, 9000001, "2026-11-03T10:00:00-05:00"),
            _post(2, 1, 8000001, "2026-11-05T09:00:00-05:00"),
        ]
        contributions, _ = build_contributions(posts, APPRENTICES, "x")
        assert contribution_status(contributions[0], date(2026, 11, 6))["status"] == "respondido_tarde"

    def test_discusion_abierta_por_el_instructor(self):
        # El instructor abre la pregunta: cada respuesta directa de aprendiz es un aporte
        posts = [
            _post(1, None, 8000001, "2026-11-03T07:00:00-05:00"),
            _post(2, 1, 9000001, "2026-11-03T10:00:00-05:00"),
            _post(3, 1, 9000002, "2026-11-03T11:00:00-05:00"),
            _post(4, 3, 8000001, "2026-11-04T08:00:00-05:00"),
            _post(5, 2, 9000003, "2026-11-04T09:00:00-05:00"),
        ]
        contributions, peers = build_contributions(posts, APPRENTICES, "x")
        assert {c["post_id"]: c["first_reply_at"] is not None for c in contributions} == {2: False, 3: True}
        assert peers == 1

    def test_ids_de_aprendices_del_snapshot(self):
        assert apprentice_ids(SNAPSHOT, "3388997") == APPRENTICES
        assert apprentice_ids(SNAPSHOT, "otra") == set()


# ─── API ────────────────────────────────────────────────────────────────────

SNAPSHOT = {
    "timestamp": "2026-11-01T05:00:00",
    "courses": [{
        "course_id": 99999, "ficha": "3388997", "course_name": "ADSO",
        "evidences": [], "students": [{"user_id": 9000001, "grades": {}}],
    }],
    "summaries": [],
    "participants": [{
        "ficha": "3388997", "course_id": 99999,
        "participants": [{"user_id": 9000002}, {"user_id": 9000003}],
    }],
    "errors": [],
}

ASSIGNMENTS = {
    "ficha": "3388997", "course_id": 99999, "updated_at": "2026-11-01T05:00:00",
    "assignments": [
        {"name": "Taller", "cmid": 1343194, "item_id": 100, "module_type": "assign"},
        {"name": "Foro temático - Fuentes", "cmid": 565694, "item_id": 200, "module_type": "forum"},
        {"name": "Foro social", "cmid": 565695, "item_id": None, "module_type": "forum"},
    ],
}


@pytest.fixture
def zajuna():
    """Cliente de Zajuna simulado: vista con 3 discusiones, todas con el hilo anidado."""
    client = MagicMock()
    client.fetch_forum_view.return_value = VIEW
    client.fetch_forum_discussion.side_effect = lambda d: THREADED.replace("600001", str(d))
    return client


@pytest.fixture
def api(tmp_path, zajuna):
    app.dependency_overrides[get_snapshot] = lambda: SNAPSHOT
    app.dependency_overrides[get_config] = get_base_config
    with (
        patch("src.store.forum_replies_store.FORUM_REPLIES_DIR", tmp_path / "forum_replies"),
        patch("src.api.routes.forums.load_assignments", return_value=ASSIGNMENTS),
        patch("src.api.routes.forums._shared_client", return_value=zajuna),
        patch("src.api.routes.forums.today_colombia", return_value=date(2026, 11, 20)),
        TestClient(app) as c,
    ):
        yield c
    app.dependency_overrides.clear()


class TestForumsApi:
    def test_lista_solo_los_foros_del_grupo(self, api):
        res = api.get("/api/fichas/3388997/foros")
        assert res.status_code == 200
        body = res.json()
        assert [f["forum_id"] for f in body["forums"]] == [565694, 565695]
        assert body["forums"][0]["graded"] is True
        assert body["forums"][1]["graded"] is False
        assert body["forums"][0]["checked_at"] is None

    def test_foro_ajeno_es_404(self, api, zajuna):
        assert api.post("/api/fichas/3388997/foros/1343194/revisar").status_code == 404
        assert api.post("/api/fichas/3388997/foros/999/revisar").status_code == 404
        zajuna.fetch_forum_view.assert_not_called()

    def test_ficha_ajena_es_404(self, api):
        assert api.get("/api/fichas/1234567/foros").status_code == 404

    def test_sin_revision_previa_es_404(self, api):
        res = api.get("/api/fichas/3388997/foros/565694/participaciones")
        assert res.status_code == 404

    def test_revisar_guarda_y_devuelve_la_bandeja(self, api):
        res = api.post("/api/fichas/3388997/foros/565694/revisar")
        assert res.status_code == 200
        body = res.json()
        assert body["total_discussions"] == 3
        assert body["peer_replies"] == 6
        assert body["counts"]["contributions"] == 3
        assert body["counts"]["replied"] == 3
        first = body["contributions"][0]
        assert first["status"] == "respondido"
        assert first["url"].endswith("/zajuna/mod/forum/discuss.php?d=5545198#p700001")

        again = api.get("/api/fichas/3388997/foros/565694/participaciones")
        assert again.status_code == 200
        assert again.json()["counts"] == body["counts"]

        listed = api.get("/api/fichas/3388997/foros").json()["forums"][0]
        assert listed["checked_at"] == body["checked_at"]
        assert listed["counts"]["replied"] == 3

    def test_hilo_que_falla_se_reintenta_y_se_reporta(self, api, zajuna):
        calls: dict[int, int] = {}

        def flaky(d):
            calls[d] = calls.get(d, 0) + 1
            if d == 5530088:
                raise FetchError("503")
            if d == 5490212 and calls[d] == 1:
                raise FetchError("timeout")
            return THREADED.replace("600001", str(d))

        zajuna.fetch_forum_discussion.side_effect = flaky
        body = api.post("/api/fichas/3388997/foros/565694/revisar").json()
        assert body["failed_discussions"] == [5530088]
        assert body["counts"]["contributions"] == 2
        assert calls[5490212] == 2

    def test_sin_aprendices_en_el_snapshot_es_409(self, api):
        app.dependency_overrides[get_snapshot] = lambda: {
            **SNAPSHOT, "participants": [],
            "courses": [{**SNAPSHOT["courses"][0], "students": []}],
        }
        assert api.post("/api/fichas/3388997/foros/565694/revisar").status_code == 409


class TestForumAlerts:
    def test_alerta_con_los_aportes_vencidos(self, api, zajuna):
        # El instructor de prueba no responde: los 3 aportes vencen
        zajuna.fetch_forum_discussion.side_effect = lambda d: THREADED.replace(
            "600001", str(d)
        ).replace("user/view.php?id=8000001", "user/view.php?id=9000003")
        api.post("/api/fichas/3388997/foros/565694/revisar")

        alerts = forum_reply_alerts("3388997", date(2026, 11, 20))
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.type == "forum_reply_overdue"
        assert alert.severity == "critical"
        assert alert.forum_id == 565694
        assert alert.item_id == 200
        assert alert.pending_count == 3
        assert "3 aportes sin réplica" in alert.message

        # Antes de vencer el plazo no hay alerta
        assert forum_reply_alerts("3388997", date(2026, 11, 3)) == []
        # Aportes de hace más de 30 días ya no alertan (siguen en la bandeja)
        assert forum_reply_alerts("3388997", date(2026, 12, 15)) == []

    def test_otro_instructor_no_ve_la_revision(self, api):
        api.post("/api/fichas/3388997/foros/565694/revisar")
        with as_instructor("2"):
            assert forum_reply_alerts("3388997", date(2026, 11, 20)) == []
