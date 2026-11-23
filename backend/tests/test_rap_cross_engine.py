"""Tests for RAP cross-reference engine."""
from __future__ import annotations

from src.api.rap_cross_engine import (
    _compute_resultado,
    _extract_rap_number,
    _get_zajuna_evidence_status,
    _normalize_desc,
    compute_rap_cross,
)

# --- Helper tests ---


class TestNormalizeDesc:
    def test_strips_leading_code(self):
        assert _normalize_desc("220501092 - ANALIZAR LOS REQUISITOS") == "analizar los requisitos"

    def test_strips_sofia_code(self):
        assert _normalize_desc("38392 - ANALIZAR LOS REQUISITOS") == "analizar los requisitos"

    def test_no_code(self):
        assert _normalize_desc("ANALIZAR LOS REQUISITOS") == "analizar los requisitos"

    def test_collapses_newlines(self):
        assert (
            _normalize_desc("220201501 - Aplicación de conocimientos de las\nciencias naturales")
            == "aplicación de conocimientos de las ciencias naturales"
        )


class TestExtractRapNumber:
    def test_zajuna_format(self):
        assert _extract_rap_number("220501092-01 - INTERPRETAR") == "1"

    def test_zajuna_code_only(self):
        assert _extract_rap_number("240201526-04") == "4"

    def test_sofia_format(self):
        assert _extract_rap_number("02  RECOLECTAR INFORMACIÓN") == "2"

    def test_sofia_format_dash_separator(self):
        # Derechos fundamentales usa "01- Reconocer..." en Sofia
        assert _extract_rap_number("01- Reconocer el trabajo") == "1"


class TestComputeResultado:
    def test_listo_para_aprobar(self):
        assert _compute_resultado("todas_aprobadas", "POR EVALUAR") == "listo_para_aprobar"

    def test_correcto(self):
        assert _compute_resultado("todas_aprobadas", "APROBADO") == "correcto"

    def test_pendiente(self):
        assert _compute_resultado("alguna_pendiente", "POR EVALUAR") == "pendiente"

    def test_con_problemas(self):
        assert _compute_resultado("alguna_desaprobada", "POR EVALUAR") == "con_problemas"

    def test_inconsistencia(self):
        assert _compute_resultado("todas_aprobadas", "NO APROBADO") == "inconsistencia"

    def test_aprobado_anticipado_pending(self):
        assert _compute_resultado("alguna_pendiente", "APROBADO") == "aprobado_anticipado"

    def test_aprobado_anticipado_desaprobada(self):
        assert _compute_resultado("alguna_desaprobada", "APROBADO") == "aprobado_anticipado"

    def test_case_insensitive_juicio(self):
        assert _compute_resultado("todas_aprobadas", "por evaluar") == "listo_para_aprobar"
        assert _compute_resultado("todas_aprobadas", "  APROBADO  ") == "correcto"


class TestGetZajunaEvidenceStatus:
    def test_todas_aprobadas(self):
        grades = {"100": {"value": "A"}, "101": {"value": "A"}}
        evidencias = [
            {"item_id": 100, "code": "EV01"},
            {"item_id": 101, "code": "EV02"},
        ]
        status, total, aprobadas = _get_zajuna_evidence_status(grades, evidencias)
        assert status == "todas_aprobadas"
        assert total == 2
        assert aprobadas == 2

    def test_alguna_pendiente(self):
        grades = {"100": {"value": "A"}, "101": {"value": "-"}}
        evidencias = [
            {"item_id": 100, "code": "EV01"},
            {"item_id": 101, "code": "EV02"},
        ]
        status, total, aprobadas = _get_zajuna_evidence_status(grades, evidencias)
        assert status == "alguna_pendiente"
        assert aprobadas == 1

    def test_alguna_desaprobada(self):
        grades = {"100": {"value": "A"}, "101": {"value": "D"}}
        evidencias = [
            {"item_id": 100, "code": "EV01"},
            {"item_id": 101, "code": "EV02"},
        ]
        status, total, aprobadas = _get_zajuna_evidence_status(grades, evidencias)
        assert status == "alguna_desaprobada"
        assert aprobadas == 1

    def test_no_item_id_skipped(self):
        grades = {"100": {"value": "A"}}
        evidencias = [
            {"item_id": 100, "code": "EV01"},
            {"item_id": None, "code": "EV02"},
        ]
        status, total, aprobadas = _get_zajuna_evidence_status(grades, evidencias)
        assert status == "todas_aprobadas"
        assert total == 1

    def test_missing_grade_is_pending(self):
        grades = {}
        evidencias = [{"item_id": 100, "code": "EV01"}]
        status, total, aprobadas = _get_zajuna_evidence_status(grades, evidencias)
        assert status == "alguna_pendiente"
        assert aprobadas == 0

    def test_empty_evidencias(self):
        status, total, aprobadas = _get_zajuna_evidence_status({}, [])
        assert status == "alguna_pendiente"
        assert total == 0


# --- Integration test ---


MOCK_SNAPSHOT = {
    "courses": [
        {
            "course_id": 89977,
            "ficha": "3388997",
            "course_name": "ADSO",
            "evidences": [
                {"item_id": 100, "name": "GA1-220501092-AA1-EV01 Infografia"},
                {"item_id": 101, "name": "GA1-220501092-AA1-EV02 Taller"},
                {"item_id": 200, "name": "GA2-220501093-AA1-EV01 Proyecto"},
            ],
            "students": [
                {
                    "user_id": 1,
                    "full_name": "JUAN BAEZ",
                    "document": "1000000007",
                    "email": "juan@test.com",
                    "grades": {
                        "100": {"value": "A", "passed": True},
                        "101": {"value": "A", "passed": True},
                        "200": {"value": "-", "passed": False},
                    },
                },
                {
                    "user_id": 2,
                    "full_name": "MARIA LOPEZ",
                    "document": "1005342881",
                    "email": "maria@test.com",
                    "grades": {
                        "100": {"value": "A", "passed": True},
                        "101": {"value": "D", "passed": False},
                        "200": {"value": "A", "passed": True},
                    },
                },
            ],
        },
    ],
}

MOCK_RAP_MAPPING = {
    "ficha": "3388997",
    "program_name": "ADSO",
    "mappings": [
        {
            "fase": "ANALISIS",
            "competencia": "220501092 - ANALIZAR LOS REQUISITOS",
            "rap": "220501092-01 - INTERPRETAR",
            "evidencias": [
                {"code": "GA1-220501092-AA1-EV01", "item_id": 100, "name": "Infografia", "matched": True},
                {"code": "GA1-220501092-AA1-EV02", "item_id": 101, "name": "Taller", "matched": True},
            ],
        },
        {
            "fase": "DISENO",
            "competencia": "220501093 - DISEÑAR LA SOLUCIÓN",
            "rap": "220501093-01 - CONSTRUIR",
            "evidencias": [
                {"code": "GA2-220501093-AA1-EV01", "item_id": 200, "name": "Proyecto", "matched": True},
            ],
        },
    ],
    "stats": {"total_raps": 2, "total_evidencias": 3, "matched_evidencias": 3, "unmatched_evidencias": 0},
}

MOCK_SOFIA_REPORT = {
    "ficha": "3388997",
    "program_name": "ADSO",
    "total_students": 2,
    "total_raps": 2,
    "students": [
        {
            "document": "1000000007",
            "full_name": "JUAN CARLOS BAEZ",
            "student_status": "EN FORMACION",
            "judgments": [
                {
                    "competencia_code": "38392",
                    "competencia_desc": "ANALIZAR LOS REQUISITOS",
                    "rap_code": "593060",
                    "rap_desc": "01 INTERPRETAR",
                    "juicio": "POR EVALUAR",
                },
                {
                    "competencia_code": "38393",
                    "competencia_desc": "DISEÑAR LA SOLUCIÓN",
                    "rap_code": "593061",
                    "rap_desc": "01 CONSTRUIR",
                    "juicio": "POR EVALUAR",
                },
            ],
        },
        {
            "document": "1005342881",
            "full_name": "MARIA LOPEZ",
            "student_status": "EN FORMACION",
            "judgments": [
                {
                    "competencia_code": "38392",
                    "competencia_desc": "ANALIZAR LOS REQUISITOS",
                    "rap_code": "593060",
                    "rap_desc": "01 INTERPRETAR",
                    "juicio": "APROBADO",
                },
                {
                    "competencia_code": "38393",
                    "competencia_desc": "DISEÑAR LA SOLUCIÓN",
                    "rap_code": "593061",
                    "rap_desc": "01 CONSTRUIR",
                    "juicio": "POR EVALUAR",
                },
            ],
        },
    ],
    "competency_map": {
        "38392 - ANALIZAR LOS REQUISITOS": "220501092 - ANALIZAR LOS REQUISITOS",
        "38393 - DISEÑAR LA SOLUCIÓN": "220501093 - DISEÑAR LA SOLUCIÓN",
    },
}


class TestComputeRapCross:
    def test_basic_cross(self):
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT
        )
        assert result["ficha"] == "3388997"
        assert result["total_students"] == 2
        assert result["total_raps"] == 2

    def test_juan_rap1_listo_para_aprobar(self):
        """JUAN: RAP1 all evidences approved + Sofia POR EVALUAR -> listo_para_aprobar."""
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT
        )
        juan = next(s for s in result["students"] if s["document"] == "1000000007")
        rap1 = next(r for r in juan["raps"] if "220501092" in r["rap"])
        assert rap1["resultado"] == "listo_para_aprobar"
        assert rap1["zajuna_status"] == "todas_aprobadas"
        assert rap1["sofia_juicio"] == "POR EVALUAR"

    def test_juan_rap2_pendiente(self):
        """JUAN: RAP2 has pending evidence + Sofia POR EVALUAR -> pendiente."""
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT
        )
        juan = next(s for s in result["students"] if s["document"] == "1000000007")
        rap2 = next(r for r in juan["raps"] if "220501093" in r["rap"])
        assert rap2["resultado"] == "pendiente"

    def test_maria_rap1_aprobado_anticipado(self):
        """MARIA: RAP1 has desaprobada evidence + Sofia APROBADO -> aprobado_anticipado."""
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT
        )
        maria = next(s for s in result["students"] if s["document"] == "1005342881")
        rap1 = next(r for r in maria["raps"] if "220501092" in r["rap"])
        assert rap1["resultado"] == "aprobado_anticipado"

    def test_maria_rap2_listo(self):
        """MARIA: RAP2 all evidences approved + Sofia POR EVALUAR -> listo_para_aprobar."""
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT
        )
        maria = next(s for s in result["students"] if s["document"] == "1005342881")
        rap2 = next(r for r in maria["raps"] if "220501093" in r["rap"])
        assert rap2["resultado"] == "listo_para_aprobar"

    def test_summary_counts(self):
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT
        )
        summary = result["summary"]
        assert summary["listo_para_aprobar"] == 2
        assert summary["pendiente"] == 1
        assert summary["aprobado_anticipado"] == 1

    def test_filter_by_document(self):
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT,
            filter_document="1000000007",
        )
        assert result["total_students"] == 1
        assert result["students"][0]["document"] == "1000000007"

    def test_filter_by_resultado(self):
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT,
            filter_resultado="listo_para_aprobar",
        )
        for student in result["students"]:
            for rap in student["raps"]:
                assert rap["resultado"] == "listo_para_aprobar"

    def test_nonexistent_ficha(self):
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "9999999", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT
        )
        assert result["total_students"] == 0

    def test_student_counts(self):
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", MOCK_RAP_MAPPING, MOCK_SOFIA_REPORT
        )
        juan = next(s for s in result["students"] if s["document"] == "1000000007")
        assert juan["listos_para_aprobar"] == 1
        assert juan["pendientes"] == 1

        maria = next(s for s in result["students"] if s["document"] == "1005342881")
        assert maria["listos_para_aprobar"] == 1
        assert maria["aprobados_anticipados"] == 1


# --- Exact matching by Sofia RAP code ---


def _mapping_with_sofia_codes():
    """Mapping using rap_sofia_code, with a competency whose Sofia
    description does NOT fuzzy-match the Zajuna one (the real 'ética' case:
    Sofia prefixes it with 'Enrique Low Murtra-')."""
    return {
        "ficha": "3388997",
        "program_name": "ADSO",
        "mappings": [
            {
                "fase": "EJECUCION",
                "competencia": "240201526 - Interactuar en el contexto productivo y social",
                "rap": "240201526-01 - PROMOVER MI DIGNIDAD",
                "rap_sofia_code": "593149",
                "evidencias": [
                    {"code": "GA9-240201526-AA1-EV01", "item_id": 100, "name": "Mapa", "matched": True},
                    {"code": "GA9-240201526-AA1-EV02", "item_id": 101, "name": "Taller", "matched": True},
                ],
            },
        ],
        "stats": {"total_raps": 1, "total_evidencias": 2, "matched_evidencias": 2, "unmatched_evidencias": 0},
    }


def _sofia_report_etica(juicio: str):
    return {
        "ficha": "3388997",
        "program_name": "ADSO",
        "total_students": 1,
        "total_raps": 1,
        "students": [
            {
                "document": "1000000007",
                "full_name": "JUAN CARLOS BAEZ",
                "student_status": "EN FORMACION",
                "judgments": [
                    {
                        "competencia_code": "36180",
                        "competencia_desc": "Enrique Low Murtra-Interactuar en el contexto productivo",
                        "rap_code": "593149",
                        "rap_desc": "01  PROMOVER MI DIGNIDAD",
                        "juicio": juicio,
                    },
                ],
            },
        ],
        "competency_map": {},
    }


class TestSofiaCodeMatching:
    def test_exact_code_match_bypasses_fuzzy_bridge(self):
        """With rap_sofia_code the juicio is found even when competency
        descriptions differ between systems (fuzzy matching would fail)."""
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", _mapping_with_sofia_codes(), _sofia_report_etica("APROBADO")
        )
        juan = result["students"][0]
        assert juan["raps"][0]["sofia_juicio"] == "APROBADO"
        assert juan["raps"][0]["resultado"] == "correcto"

    def test_without_code_fuzzy_fails_and_defaults_por_evaluar(self):
        """Same scenario minus rap_sofia_code: the fuzzy bridge cannot match
        'Enrique Low Murtra-...' and the juicio falls back to POR EVALUAR."""
        mapping = _mapping_with_sofia_codes()
        mapping["mappings"][0]["rap_sofia_code"] = ""
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", mapping, _sofia_report_etica("APROBADO")
        )
        juan = result["students"][0]
        assert juan["raps"][0]["sofia_juicio"] == "POR EVALUAR"

    def test_no_aprobado_inconsistencia(self):
        result = compute_rap_cross(
            MOCK_SNAPSHOT, "3388997", _mapping_with_sofia_codes(), _sofia_report_etica("NO APROBADO")
        )
        juan = result["students"][0]
        assert juan["raps"][0]["resultado"] == "inconsistencia"
