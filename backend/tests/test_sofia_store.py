"""Tests for Sofia Plus report store."""
from __future__ import annotations

import json
from unittest.mock import patch

from src.store.sofia_store import (
    delete_sofia_report,
    load_sofia_report,
    save_sofia_report,
)

SAMPLE_REPORT = {
    "program_name": "ANALISIS Y DESARROLLO DE SOFTWARE",
    "total_students": 44,
    "total_raps": 75,
    "students": [
        {
            "document": "1000000007",
            "full_name": "JUAN CARLOS BAEZ",
            "student_status": "EN FORMACION",
            "judgments": [
                {
                    "competencia_code": "38392",
                    "competencia_desc": "ANALIZAR LOS REQUISITOS DEL CLIENTE",
                    "rap_code": "593060",
                    "rap_desc": "01 DEFINIR LAS CARACTERÍSTICAS",
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
                    "competencia_desc": "ANALIZAR LOS REQUISITOS DEL CLIENTE",
                    "rap_code": "593060",
                    "rap_desc": "01 DEFINIR LAS CARACTERÍSTICAS",
                    "juicio": "APROBADO",
                },
            ],
        },
    ],
    "competency_map": {
        "38392 - ANALIZAR LOS REQUISITOS DEL CLIENTE": "220501092 - ANALIZAR LOS REQUISITOS",
    },
}


class TestSofiaStore:
    def test_save_and_load(self, tmp_path):
        with patch("src.store.sofia_store.SOFIA_REPORTS_DIR", tmp_path):
            result = save_sofia_report("3388997", {**SAMPLE_REPORT})
            assert result["ficha"] == "3388997"
            assert result["total_students"] == 44
            assert "uploaded_at" in result

            loaded = load_sofia_report("3388997")
            assert loaded is not None
            assert loaded["ficha"] == "3388997"
            assert len(loaded["students"]) == 2

    def test_load_nonexistent(self, tmp_path):
        with patch("src.store.sofia_store.SOFIA_REPORTS_DIR", tmp_path):
            result = load_sofia_report("9999999")
            assert result is None

    def test_delete_existing(self, tmp_path):
        with patch("src.store.sofia_store.SOFIA_REPORTS_DIR", tmp_path):
            save_sofia_report("3388997", {**SAMPLE_REPORT})
            assert delete_sofia_report("3388997") is True
            assert load_sofia_report("3388997") is None

    def test_delete_nonexistent(self, tmp_path):
        with patch("src.store.sofia_store.SOFIA_REPORTS_DIR", tmp_path):
            assert delete_sofia_report("9999999") is False

    def test_save_overwrites(self, tmp_path):
        with patch("src.store.sofia_store.SOFIA_REPORTS_DIR", tmp_path):
            save_sofia_report("3388997", {"students": [], "total_students": 0, "total_raps": 0})
            save_sofia_report("3388997", {**SAMPLE_REPORT})
            loaded = load_sofia_report("3388997")
            assert loaded["total_students"] == 44
            assert len(loaded["students"]) == 2

    def test_creates_directory(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        with patch("src.store.sofia_store.SOFIA_REPORTS_DIR", nested):
            save_sofia_report("3388997", {"students": [], "total_students": 0, "total_raps": 0})
            assert nested.exists()

    def test_file_content_is_valid_json(self, tmp_path):
        with patch("src.store.sofia_store.SOFIA_REPORTS_DIR", tmp_path):
            save_sofia_report("3388997", {**SAMPLE_REPORT})
            # Guarda en la carpeta del instructor (el "1" de los tests)
            raw = (tmp_path / "1" / "3388997.json").read_text(encoding="utf-8")
            data = json.loads(raw)
            assert data["ficha"] == "3388997"
            assert "students" in data
            assert "competency_map" in data
