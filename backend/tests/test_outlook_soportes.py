"""Soportes de llamados desde Outlook: asuntos, ZIP, sesión, impresión y rutas (sin Chrome ni Outlook reales)."""
from __future__ import annotations

import base64
import io
import json
import time
import zipfile
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.routes import outlook_soportes
from src.api.server import app
from src.outlook import llamados
from src.outlook.export_jobs import ExportJobs
from src.outlook.llamados import PdfEntry, build_zip, classify_subject, zip_filename
from src.outlook.mail_client import (
    COLOMBIA_TZ,
    MailApiError,
    SentMessage,
    _day_bounds_utc,
    _to_message,
)
from src.outlook.printer import message_url
from src.outlook.session import (
    OutlookConnection,
    OutlookCredentials,
    OutlookSessionManager,
    credentials_from_tokens,
)

from tests.conftest import make_cmm_token

FICHA = "3389000"
SNAPSHOT = {"courses": [{"ficha": FICHA, "students": []}]}


def _jwt(claims: dict) -> str:
    def enc(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{enc({'alg': 'none'})}.{enc(claims)}.firma"


def _msg(mid: str, subject: str, day: int = 29, hour: int = 10) -> SentMessage:
    return SentMessage(
        id=mid,
        subject=subject,
        sent_at=datetime(2026, 10, day, hour, 0, tzinfo=COLOMBIA_TZ),
        to=["aprendiz@soy.sena.edu.co"],
    )


# --- Asuntos ---


@pytest.mark.parametrize(
    "subject, stage, name",
    [
        ("Primer llamado de atención - Ficha 3389000 - ANA PÉREZ", "primer_llamado", "ANA PÉREZ"),
        ("Segundo llamado de atencion - Ficha 3389000 - JUAN RUIZ", "segundo_llamado", "JUAN RUIZ"),
        ("Plan de mejoramiento - Ficha 3389000 - LUZ DÍAZ", "plan_mejoramiento", "LUZ DÍAZ"),
        ("Remisión a Comité de Evaluación - Ficha 3389000 - EVA SOL", "comite", "EVA SOL"),
        ("TERCER LLAMADO - Grupo 3389000 - PEPE", "tercer_llamado", "PEPE"),
    ],
)
def test_classify_subject(subject, stage, name):
    info = classify_subject(subject)
    assert info is not None
    assert (info.stage, info.ficha, info.student_name) == (stage, FICHA, name)


@pytest.mark.parametrize(
    "subject",
    [
        "RE: Primer llamado de atención - Ficha 3389000 - ANA PÉREZ",
        "RV: Plan de mejoramiento - Ficha 3389000 - LUZ DÍAZ",
        "Sofia Plus no permite evaluar a un aprendiz",
    ],
)
def test_classify_subject_descarta_respuestas_y_otros(subject):
    assert classify_subject(subject) is None


def test_build_zip_agrupa_por_etapa_y_no_pisa_nombres():
    entries = [
        PdfEntry("segundo_llamado", "JUAN RUIZ", "s", "2026-10-29", b"%PDF-2"),
        PdfEntry("primer_llamado", "ANA/PÉREZ", "s", "2026-10-02", b"%PDF-1"),
        PdfEntry("primer_llamado", "ANA/PÉREZ", "s", "2026-10-02", b"%PDF-1b"),
    ]
    data, paths = build_zip(entries)
    assert paths[0] == "2. Segundo llamado/JUAN RUIZ - 2026-10-29.pdf"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert sorted(zf.namelist()) == [
            "1. Primer llamado/ANA-PÉREZ - 2026-10-02 (2).pdf",
            "1. Primer llamado/ANA-PÉREZ - 2026-10-02.pdf",
            "2. Segundo llamado/JUAN RUIZ - 2026-10-29.pdf",
        ]


@pytest.mark.parametrize(
    "stages, day, expected",
    [
        ({"comite"}, date(2026, 10, 29), "Comite_3389000_29-10-26.zip"),
        ({"primer_llamado", "plan_mejoramiento"}, date(2026, 10, 2), "Llamados_3389000_02-10-26.zip"),
    ],
)
def test_zip_filename_con_fecha_numerica(stages, day, expected):
    assert zip_filename(FICHA, stages, day) == expected


def test_stage_folders_en_orden():
    assert list(llamados.STAGE_FOLDERS.values())[0].startswith("1.")


# --- Cliente de Outlook ---


def test_dia_en_hora_de_colombia():
    assert _day_bounds_utc(date(2026, 10, 29)) == ("2026-10-29T05:00:00Z", "2026-10-30T05:00:00Z")


def test_to_message_pasa_utc_a_colombia_y_lee_camel_case():
    msg = _to_message(
        {
            "id": "abc",
            "subject": "x",
            "sentDateTime": "2026-10-30T02:30:00.1234567Z",
            "toRecipients": [{"emailAddress": {"address": "a@b.co"}}],
        }
    )
    assert msg.sent_at.date() == date(2026, 10, 29)  # 9:30 p. m. del 29 en Colombia
    assert msg.to == ["a@b.co"]


def test_message_url_abre_el_correo_sin_redireccion():
    # El WebLink (/owa/?ItemID=) redirige y Outlook bloquea tras ~10 redirecciones seguidas.
    assert message_url("https://outlook.office365.com", "AQMk+a/b==") == (
        "https://outlook.office365.com/mail/deeplink/read/AQMk%2Ba%2Fb%3D%3D"
    )


# --- Sesión ---


class _FakeProbeClient:
    def __init__(self, token, base, style):
        self.base = base

    def probe(self):
        if "graph" in self.base:
            raise MailApiError("no", status=403)


def test_credentials_from_tokens_elige_el_que_responde():
    exp = int(time.time()) + 3600
    vencido = _jwt({"aud": "https://outlook.office.com", "exp": int(time.time()) - 10})
    graph = _jwt({"aud": "https://graph.microsoft.com", "exp": exp})
    outlook = _jwt({"aud": "https://outlook.office.com", "exp": exp, "upn": "yo@sena.edu.co"})
    creds = credentials_from_tokens([vencido, graph, outlook], client_factory=_FakeProbeClient)
    assert creds is not None
    assert creds.token == outlook
    assert creds.account == "yo@sena.edu.co"
    assert creds.base == "https://outlook.office.com/api/v2.0"


def _conn(minutes: int = 60) -> OutlookConnection:
    return OutlookConnection(
        creds=OutlookCredentials(
            token="t",
            base="https://outlook.office.com/api/v2.0",
            style="pascal",
            account="yo@sena.edu.co",
            expires_at=datetime.now(UTC) + timedelta(minutes=minutes),
        )
    )


def _wait_for(manager, user_id, status):
    for _ in range(500):
        if manager.status(user_id)["status"] == status:
            return
        time.sleep(0.01)
    raise AssertionError(manager.status(user_id))


def test_session_manager_conecta_y_vence():
    manager = OutlookSessionManager(login_fn=lambda on_waiting: _conn())
    assert manager.start_login("7")["status"] == "waiting_login"
    _wait_for(manager, "7", "connected")
    assert manager.status("7")["account"] == "yo@sena.edu.co"
    assert manager.status("8")["status"] == "idle"  # otro instructor no la ve

    manager._states["7"].conn = _conn(minutes=1)  # dentro del margen de vencimiento
    assert manager.connection("7") is None
    assert manager.status("7")["status"] == "idle"


def test_session_manager_detecta_chrome_cerrado():
    class _ClosedChrome:
        def is_running(self):
            return False

        def close(self):
            pass

    conn = _conn()
    conn.chrome = _ClosedChrome()
    manager = OutlookSessionManager(login_fn=lambda on_waiting: conn)
    manager.start_login("7")
    for _ in range(500):
        if manager._states["7"].conn is conn:
            break
        time.sleep(0.01)
    assert manager.connection("7") is None
    assert "Chrome" in manager.status("7")["message"]


def test_session_manager_informa_error_sin_detalles():
    def falla(on_waiting):
        raise ValueError("token secreto")

    manager = OutlookSessionManager(login_fn=falla)
    manager.start_login("7")
    _wait_for(manager, "7", "error")
    assert "secreto" not in manager.status("7")["message"]


# --- Rutas ---


class _FakeMailClient:
    MESSAGES = {
        "a": _msg("a", "Primer llamado de atención - Ficha 3389000 - ANA PÉREZ", day=2),
        "b": _msg("b", "Segundo llamado de atención - Ficha 3389000 - JUAN RUIZ", day=29),
        "c": _msg("c", "Plan de mejoramiento - Ficha 3388997 - OTRO GRUPO", day=29),
        "d": _msg("d", "RE: Primer llamado de atención - Ficha 3389000 - ANA PÉREZ", day=29),
        "e": _msg("e", "Remisión a Comité de Evaluación - Ficha 3389000 - EVA SOL", day=29),
    }

    def __init__(self):
        self.fail_status: int | None = None

    def list_sent_on(self, day):
        if self.fail_status:
            raise MailApiError("x", status=self.fail_status)
        return [m for m in self.MESSAGES.values() if m.sent_at.date() == day]

    def get_message(self, mid):
        if self.fail_status:
            raise MailApiError("x", status=self.fail_status)
        return self.MESSAGES[mid]


class _FakePrinter:
    """Hace las veces de "Imprimir" de Outlook: un PDF por correo."""

    printed: list[tuple[str, str]] = []

    def __init__(self, chrome, page):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def print_pdf(self, message_id, needle):
        self.printed.append((message_id, needle))
        return b"%PDF-fake"


@pytest.fixture
def client(monkeypatch):
    manager = OutlookSessionManager(login_fn=lambda on_waiting: _conn())
    monkeypatch.setattr(outlook_soportes, "session_manager", manager)
    fake = _FakeMailClient()
    monkeypatch.setattr(OutlookCredentials, "client", lambda self: fake)
    _FakePrinter.printed = []
    recorded: list[tuple[str, list[dict], str]] = []
    monkeypatch.setattr(
        outlook_soportes,
        "export_jobs",
        ExportJobs(printer_factory=_FakePrinter, record_fn=lambda f, e, z: recorded.append((f, e, z))),
    )
    _FakePrinter.recorded = recorded
    app.dependency_overrides[get_snapshot] = lambda: SNAPSHOT
    yield TestClient(app), manager, fake
    app.dependency_overrides.clear()


def _connect(manager):
    manager.start_login("1")  # el token de los tests es del usuario "1"
    _wait_for(manager, "1", "connected")


def _wait_job(tc, job_id):
    for _ in range(500):
        data = tc.get(f"/api/fichas/{FICHA}/soportes-llamados/zip/{job_id}").json()
        if data["status"] != "running":
            return data
        time.sleep(0.01)
    raise AssertionError(data)


def test_buscar_exige_outlook_conectado(client):
    tc, _manager, _fake = client
    resp = tc.post(f"/api/fichas/{FICHA}/soportes-llamados/buscar", json={"fechas": ["2026-10-29"]})
    assert resp.status_code == 409


def test_buscar_filtra_grupo_etapa_y_respuestas(client):
    tc, manager, _fake = client
    _connect(manager)
    resp = tc.post(
        f"/api/fichas/{FICHA}/soportes-llamados/buscar",
        json={"fechas": ["2026-10-02", "2026-10-29"], "etapas": ["primer_llamado", "comite"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert [c["id"] for c in data["correos"]] == ["a", "e"]
    assert data["correos"][0]["sent_date"] == "2026-10-02"
    assert data["revisados"] == 5


def test_buscar_rechaza_ficha_ajena_y_etapa_desconocida(client):
    tc, manager, _fake = client
    _connect(manager)
    assert tc.post("/api/fichas/999/soportes-llamados/buscar", json={"fechas": ["2026-10-29"]}).status_code == 404
    resp = tc.post(f"/api/fichas/{FICHA}/soportes-llamados/buscar", json={"fechas": ["2026-10-29"], "etapas": ["x"]})
    assert resp.status_code == 422


def test_token_vencido_desconecta(client):
    tc, manager, fake = client
    _connect(manager)
    fake.fail_status = 401
    resp = tc.post(f"/api/fichas/{FICHA}/soportes-llamados/buscar", json={"fechas": ["2026-10-29"]})
    assert resp.status_code == 409
    assert manager.status("1")["status"] == "idle"


def test_zip_imprime_con_outlook_y_saca_un_zip_por_dia(client):
    tc, manager, _fake = client
    _connect(manager)
    start = tc.post(f"/api/fichas/{FICHA}/soportes-llamados/zip", json={"message_ids": ["b", "e", "a"]})
    assert start.status_code == 200
    assert start.json()["total"] == 3
    job = _wait_job(tc, start.json()["job_id"])
    assert job["status"] == "done" and job["done"] == 3
    # Cada PDF sale de "Imprimir" en Outlook Web, en el orden pedido.
    assert [mid for mid, _ in _FakePrinter.printed] == ["b", "e", "a"]
    # Un ZIP por día de envío, del más antiguo al más reciente.
    assert job["archivos"] == ["Primer_llamado_3389000_02-10-26.zip", "Llamados_3389000_29-10-26.zip"]
    contents = []
    for i, name in enumerate(job["archivos"]):
        resp = tc.get(f"/api/fichas/{FICHA}/soportes-llamados/zip/{job['job_id']}/archivo/{i}")
        assert resp.status_code == 200
        assert f'filename="{name}"' in resp.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            contents.append(sorted(zf.namelist()))
    assert contents == [
        ["1. Primer llamado/ANA PÉREZ - 2026-10-02.pdf"],
        ["2. Segundo llamado/JUAN RUIZ - 2026-10-29.pdf", "5. Comite de evaluacion/EVA SOL - 2026-10-29.pdf"],
    ]
    assert tc.get(f"/api/fichas/{FICHA}/soportes-llamados/zip/{job['job_id']}/archivo/2").status_code == 404
    # Queda registro por aprendiz de qué se imprimió y en qué ZIP.
    recorded = {zip_name: [(e["message_id"], e["archivo"]) for e in entries] for _f, entries, zip_name in _FakePrinter.recorded}
    assert recorded == {
        "Primer_llamado_3389000_02-10-26.zip": [("a", "1. Primer llamado/ANA PÉREZ - 2026-10-02.pdf")],
        "Llamados_3389000_29-10-26.zip": [
            ("b", "2. Segundo llamado/JUAN RUIZ - 2026-10-29.pdf"),
            ("e", "5. Comite de evaluacion/EVA SOL - 2026-10-29.pdf"),
        ],
    }


def test_zip_no_acepta_correos_de_otro_grupo(client):
    tc, manager, _fake = client
    _connect(manager)
    start = tc.post(f"/api/fichas/{FICHA}/soportes-llamados/zip", json={"message_ids": ["a", "c"]})
    job = _wait_job(tc, start.json()["job_id"])
    assert job["status"] == "error"
    assert FICHA in job["message"]
    assert _FakePrinter.printed == []
    assert tc.get(f"/api/fichas/{FICHA}/soportes-llamados/zip/{job['job_id']}/archivo/0").status_code == 409


def test_zip_de_otro_instructor_no_se_ve(client):
    tc, manager, _fake = client
    _connect(manager)
    start = tc.post(f"/api/fichas/{FICHA}/soportes-llamados/zip", json={"message_ids": ["a"]})
    job_id = start.json()["job_id"]
    _wait_job(tc, job_id)
    otro = TestClient(app, headers={"Authorization": f"Bearer {make_cmm_token(sub='2')}"})
    assert otro.get(f"/api/fichas/{FICHA}/soportes-llamados/zip/{job_id}/archivo/0").status_code == 404


def test_zip_token_vencido_desconecta(client):
    tc, manager, fake = client
    _connect(manager)
    fake.fail_status = 401
    start = tc.post(f"/api/fichas/{FICHA}/soportes-llamados/zip", json={"message_ids": ["a"]})
    job = _wait_job(tc, start.json()["job_id"])
    assert job["status"] == "error"
    assert manager.status("1")["status"] == "idle"


def test_session_routes(client):
    tc, _manager, _fake = client
    assert tc.get("/api/outlook/session").json()["status"] == "idle"
    assert tc.post("/api/outlook/session").json()["status"] == "waiting_login"
    assert tc.delete("/api/outlook/session").status_code == 200
