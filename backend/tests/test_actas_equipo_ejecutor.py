"""Actas del equipo ejecutor: datos del día, Word generado, registro de soportes y rutas."""
from __future__ import annotations

import io
from datetime import date

import docx
import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.routes import actas_equipo_ejecutor
from src.api.server import app
from src.outlook.acta import ActaInput, Asistente, build_acta, collect_llamados
from src.store import soportes_store

FICHA = "3389000"
SNAPSHOT = {
    "courses": [
        {"ficha": FICHA, "students": [{"user_id": 9, "full_name": "Eva Sol Luna", "document": "999"}]},
    ]
}
DUE = [
    {
        "full_name": "ANA PÉREZ",
        "document": "111",
        "history": [
            {"stage": "primer_llamado", "date": "2026-10-02T10:00:00"},
            {"stage": "segundo_llamado", "date": "2026-10-29T09:00:00"},
        ],
    },
    {"full_name": "JUAN RUIZ", "document": "222", "history": [{"stage": "plan_mejoramiento", "date": "2026-10-02T10:00:00"}]},
]
SOPORTES = [
    {
        "message_id": "m1",
        "stage": "primer_llamado",
        "student_name": "ANA PEREZ",  # el asunto puede venir sin tilde
        "subject": "Primer llamado - Ficha 3389000 - ANA PEREZ",
        "sent_at": "2026-10-02T12:53:00-05:00",
        "to": ["ana@x.co"],
        "archivo": "1. Primer llamado/ANA PEREZ - 2026-10-02.pdf",
    },
    {
        "message_id": "m2",
        "stage": "comite",
        "student_name": "EVA SOL LUNA",
        "subject": "Remisión a Comité - Ficha 3389000 - EVA SOL LUNA",
        "sent_at": "2026-10-02T13:05:00-05:00",
        "to": ["eva@x.co"],
        "archivo": "5. Comite de evaluacion/EVA SOL LUNA - 2026-10-02.pdf",
    },
]


def _text(content: bytes) -> str:
    d = docx.Document(io.BytesIO(content))
    out = []

    def walk(tables):
        for t in tables:
            for row in t.rows:
                for cell in row.cells:
                    out.extend(p.text for p in cell.paragraphs)
                    walk(cell.tables)

    walk(d.tables)
    return "\n".join(out)


def test_collect_llamados_cruza_debido_proceso_y_soportes():
    llamados, del_dia = collect_llamados(DUE, SOPORTES, date(2026, 10, 2), {"eva sol luna": "999"})
    assert [(ll.nombre, ll.stage, ll.hora_envio, ll.documento) for ll in llamados] == [
        ("ANA PÉREZ", "primer_llamado", "12:53 p. m.", "111"),
        ("JUAN RUIZ", "plan_mejoramiento", "", "222"),  # registrado sin soporte descargado
        ("EVA SOL LUNA", "comite", "1:05 p. m.", "999"),  # soporte sin registro en la app
    ]
    assert len(del_dia) == 2
    assert collect_llamados(DUE, SOPORTES, date(2026, 10, 5))[0] == []


def test_build_acta_llena_la_plantilla_sin_marcadores():
    llamados, _ = collect_llamados(DUE, SOPORTES, date(2026, 10, 2))
    content = build_acta(
        ActaInput(
            numero="17",
            ficha=FICHA,
            fecha_envio=date(2026, 10, 2),
            fecha_acta=date(2026, 10, 3),
            hora_inicio="08:00 p.m.",
            hora_fin="09:00 p.m.",
            asistentes=[Asistente("Instructor Uno"), Asistente("Instructor Dos", "SENA/CMM")],
            llamados=llamados,
            anexo_zip="Llamados_3389000_02-10-26.zip",
            soportes=2,
        )
    )
    text = _text(content)
    assert "{{" not in text
    assert "ACTA No. 17" in text
    assert "3 de octubre de 2026" in text  # fecha del acta
    assert "1 primer llamado de atención" in text and "1 plan de mejoramiento" in text
    assert "ANA PÉREZ" in text and "12:53 p. m." in text
    assert "Instructor Uno" in text and "Instructor Dos" in text
    assert "Llamados_3389000_02-10-26.zip" in text
    # La relación va en una tabla anidada: No., Aprendiz, Documento, Etapa, Hora de envío.
    d = docx.Document(io.BytesIO(content))
    nested = [t for row in d.tables[0].rows for c in row.cells for t in c.tables]
    assert nested and nested[0].rows[0].cells[1].text == "Aprendiz"
    assert len(nested[0].rows) == 1 + len(llamados)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(soportes_store, "SOPORTES_DIR", tmp_path / "soportes")
    monkeypatch.setattr(soportes_store, "ACTAS_DIR", tmp_path / "actas")
    monkeypatch.setattr(
        actas_equipo_ejecutor, "load_due_process", lambda ficha: {"records": {str(i): r for i, r in enumerate(DUE)}}
    )
    soportes_store.record_soportes(FICHA, SOPORTES, "Llamados_3389000_02-10-26.zip")
    app.dependency_overrides[get_snapshot] = lambda: SNAPSHOT
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_actas_lista_fechas_y_soportes(client):
    data = client.get(f"/api/fichas/{FICHA}/actas-equipo-ejecutor").json()
    assert [f["fecha_envio"] for f in data["fechas"]] == ["2026-10-29", "2026-10-02"]
    oct2 = data["fechas"][1]
    assert oct2["por_etapa"] == {"primer_llamado": 1, "plan_mejoramiento": 1}
    assert oct2["soportes"] == 2 and oct2["acta_numero"] is None
    assert data["siguiente_numero"] == 1
    assert {s["message_id"] for s in data["soportes"]} == {"m1", "m2"}
    assert client.get("/api/fichas/999/actas-equipo-ejecutor").status_code == 404


def test_post_acta_devuelve_word_y_recuerda_datos(client):
    body = {
        "fecha_envio": "2026-10-02",
        "numero": 17,
        "hora_inicio": "08:00 p.m.",
        "hora_fin": "09:00 p.m.",
        "asistentes": [{"nombre": "Instructor Uno", "dependencia": "SENA/CMM"}],
    }
    resp = client.post(f"/api/fichas/{FICHA}/actas-equipo-ejecutor", json=body)
    assert resp.status_code == 200
    assert 'filename="ACTA_EQUIPO_EJECUTOR_02-10-26.docx"' in resp.headers["content-disposition"]
    # El nombre lleva la fecha del acta, no la del envío.
    resp = client.post(f"/api/fichas/{FICHA}/actas-equipo-ejecutor", json={**body, "fecha_acta": "2026-10-15"})
    assert 'filename="ACTA_EQUIPO_EJECUTOR_15-10-26.docx"' in resp.headers["content-disposition"]
    text = _text(resp.content)
    assert "EVA SOL LUNA" in text and "999" in text  # documento tomado del grupo
    data = client.get(f"/api/fichas/{FICHA}/actas-equipo-ejecutor").json()
    assert data["siguiente_numero"] == 18
    assert data["asistentes"] == [{"nombre": "Instructor Uno", "dependencia": "SENA/CMM"}]
    assert data["fechas"][1]["acta_numero"] == 17


def test_post_acta_sin_llamados_ese_dia(client):
    body = {"fecha_envio": "2026-10-05", "numero": 1, "hora_inicio": "8", "hora_fin": "9", "asistentes": [{"nombre": "X"}]}
    assert client.post(f"/api/fichas/{FICHA}/actas-equipo-ejecutor", json=body).status_code == 404
