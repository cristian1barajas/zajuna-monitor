"""Juicios por asignar en Sofía: listas de aprobar / no aprobar por competencia y RAP."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.juicios_por_asignar import compute_juicios_por_asignar
from src.api.server import app

FICHA = "3389000"
EV1, EV2, EV3 = 101, 102, 103


def _student(doc, name, grades):
    return {"user_id": int(doc), "document": doc, "full_name": name, "grades": {str(k): {"value": v} for k, v in grades.items()}}


SNAPSHOT = {
    "courses": [
        {
            "ficha": FICHA,
            "evidences": [{"item_id": EV1}, {"item_id": EV2}, {"item_id": EV3}],
            "students": [
                _student("1", "ZOE ÁLVAREZ", {EV1: "A", EV2: "A"}),  # todo aprobado → aprobar
                _student("2", "ÁNGELA RUIZ", {EV1: "A", EV2: "A"}),  # aprobar (orden alfabético sin tildes)
                _student("3", "CARLOS DÍAZ", {EV1: "A", EV2: "D"}),  # una D → no aprobar
                _student("4", "BETTY SOL", {EV1: "A"}),  # EV2 sin nota y dentro del corte → no aprobar
                _student("5", "DORA PAZ", {EV1: "A", EV2: "A"}),  # ya APROBADO en Sofía → no sale
                _student("6", "ELENA MAR", {EV1: "A", EV2: "A"}),  # CANCELADO en Sofía → no sale
                _student("7", "FABIO LUZ", {EV3: "A"}),  # RAP 2: le falta EV1; cuenta solo si EV1 está en el corte
            ],
        }
    ]
}

MAPPING = {
    "mappings": [
        {
            "fase": "ANÁLISIS",
            "competencia": "220501092 - Establecer requisitos",
            "rap": "220501092-01 - Caracterizar procesos",
            "rap_sofia_code": "593346",
            "evidencias": [{"code": "EV1", "item_id": EV1}, {"code": "EV2", "item_id": EV2}],
        },
        {
            "fase": "PLANEACIÓN",
            "competencia": "220501097- Implementar la solución",
            "rap": "220501097-02 - Instalar",
            "rap_sofia_code": "593400",
            "evidencias": [{"code": "EV3", "item_id": EV3}, {"code": "EV1", "item_id": EV1}],
        },
    ]
}


def _judgments(juicio_rap1="POR EVALUAR"):
    return [
        {"competencia_code": "37001", "competencia_desc": "ESTABLECER REQUISITOS", "rap_code": "593346",
         "rap_desc": "01 CARACTERIZAR LOS PROCESOS", "juicio": juicio_rap1},
        {"competencia_code": "37002", "competencia_desc": "IMPLEMENTAR LA SOLUCIÓN", "rap_code": "593400",
         "rap_desc": "02 INSTALAR", "juicio": "POR EVALUAR"},
    ]


SOFIA = {
    "students": [
        {"document": "1", "full_name": "ZOE ÁLVAREZ", "student_status": "EN FORMACION", "judgments": _judgments()},
        {"document": "2", "full_name": "ÁNGELA RUIZ", "student_status": "EN FORMACIÓN", "judgments": _judgments()},
        {"document": "3", "full_name": "CARLOS DÍAZ", "student_status": "EN FORMACION", "judgments": _judgments()},
        {"document": "4", "full_name": "BETTY SOL", "student_status": "EN FORMACION", "judgments": _judgments()},
        {"document": "5", "full_name": "DORA PAZ", "student_status": "EN FORMACION", "judgments": _judgments("APROBADO")},
        {"document": "6", "full_name": "ELENA MAR", "student_status": "CANCELADO", "judgments": _judgments()},
        {"document": "7", "full_name": "FABIO LUZ", "student_status": "EN FORMACION", "judgments": _judgments()},
    ]
}


def test_listas_por_rap_en_orden_alfabetico():
    r = compute_juicios_por_asignar(SNAPSHOT, FICHA, MAPPING, SOFIA, {EV1, EV2})
    assert r["fuera_de_formacion"] == 1

    [aprobar] = r["aprobar"]
    assert (aprobar["competencia_code"], aprobar["competencia_programa"], aprobar["rap_code"]) == ("37001", "220501092", "593346")
    assert aprobar["rap_desc"] == "01 CARACTERIZAR LOS PROCESOS"  # texto tal como está en Sofía
    assert [a["full_name"] for a in aprobar["aprendices"]] == ["ÁNGELA RUIZ", "ZOE ÁLVAREZ"]

    assert [x["rap_code"] for x in r["no_aprobar"]] == ["593346", "593400"]
    rap1, rap2 = r["no_aprobar"]
    assert [(a["full_name"], a["desaprobadas"], a["sin_entregar"]) for a in rap1["aprendices"]] == [
        ("BETTY SOL", 0, 1),
        ("CARLOS DÍAZ", 1, 0),
        ("FABIO LUZ", 0, 2),
    ]
    assert [a["full_name"] for a in rap2["aprendices"]] == ["FABIO LUZ"]
    assert rap2["competencia_programa"] == "220501097"  # "220501097- Implementar" sin espacio


def test_el_corte_decide_que_cuenta_como_no_entregado():
    # EV1 fuera del corte: que a FABIO le falte no lo deja en no aprobar.
    r = compute_juicios_por_asignar(SNAPSHOT, FICHA, MAPPING, SOFIA, {EV2})
    assert [x["rap_code"] for x in r["no_aprobar"]] == ["593346"]
    # Sin selección no hay evidencias que ya debieran estar: solo cuentan las D.
    r = compute_juicios_por_asignar(SNAPSHOT, FICHA, MAPPING, SOFIA, set())
    assert [a["full_name"] for a in r["no_aprobar"][0]["aprendices"]] == ["CARLOS DÍAZ"]


def test_ruta_juicios_por_asignar():
    app.dependency_overrides[get_snapshot] = lambda: SNAPSHOT
    try:
        tc = TestClient(app)
        with patch("src.api.routes.juicios.load_rap_mapping", return_value=MAPPING), patch(
            "src.api.routes.juicios.load_sofia_report", return_value=SOFIA
        ):
            resp = tc.post(f"/api/fichas/{FICHA}/juicios-por-asignar", json={"evidence_ids": [EV1, EV2]})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["aprobar"][0]["aprendices"]) == 2
            assert tc.post("/api/fichas/999/juicios-por-asignar", json={"evidence_ids": []}).status_code == 404
        with patch("src.api.routes.juicios.load_rap_mapping", return_value=None):
            assert tc.post(f"/api/fichas/{FICHA}/juicios-por-asignar", json={}).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_excluye_novedades_y_suspendidos():
    snapshot = {
        **SNAPSHOT,
        "courses": [{**SNAPSHOT["courses"][0], "course_id": 89964}],
        "participants": [
            {"course_id": 89964, "participants": [{"user_id": 2, "status": "Suspendido"}, {"user_id": 1, "status": "Activo"}]}
        ],
    }
    # 2 (ÁNGELA) suspendida en Zajuna; 3 (CARLOS) con novedad registrada.
    r = compute_juicios_por_asignar(snapshot, FICHA, MAPPING, SOFIA, {EV1, EV2}, novedad_ids={3})
    assert (r["suspendidos"], r["con_novedad"], r["fuera_de_formacion"]) == (1, 1, 1)
    assert [a["full_name"] for a in r["aprobar"][0]["aprendices"]] == ["ZOE ÁLVAREZ"]
    nombres = {a["full_name"] for rap in r["no_aprobar"] for a in rap["aprendices"]}
    assert "CARLOS DÍAZ" not in nombres and "ÁNGELA RUIZ" not in nombres
