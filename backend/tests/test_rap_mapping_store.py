"""Tests for RAP mapping store."""
from __future__ import annotations

import json
from unittest.mock import patch

from src.store.rap_mapping_store import (
    delete_rap_mapping,
    load_rap_mapping,
    save_rap_mapping,
)

SAMPLE_MAPPING = {
    "program_name": "ANALISIS Y DESARROLLO DE SOFTWARE",
    "mappings": [
        {
            "fase": "ANALISIS",
            "competencia": "220501092 - ANALIZAR LOS REQUISITOS",
            "rap": "220501092-01 - INTERPRETAR",
            "evidencias": [
                {"code": "GA1-220501092-AA1-EV01", "item_id": 2506476, "name": "Infografia", "matched": True},
                {"code": "GA1-220501092-AA1-EV02", "item_id": 2506477, "name": "Taller", "matched": True},
            ],
        },
        {
            "fase": "DISENO",
            "competencia": "220501093 - DISEÑAR",
            "rap": "220501093-01 - CONSTRUIR",
            "evidencias": [
                {"code": "GA2-220501093-AA1-EV01", "item_id": None, "name": "Proyecto", "matched": False},
            ],
        },
    ],
    "stats": {"total_raps": 2, "total_evidencias": 3, "matched_evidencias": 2, "unmatched_evidencias": 1},
}


class TestRapMappingStore:
    def test_save_and_load(self, tmp_path):
        with patch("src.store.rap_mapping_store.RAP_MAPPINGS_DIR", tmp_path):
            result = save_rap_mapping("3388997", {**SAMPLE_MAPPING})
            assert result["ficha"] == "3388997"
            assert result["program_name"] == "ANALISIS Y DESARROLLO DE SOFTWARE"
            assert "updated_at" in result

            loaded = load_rap_mapping("3388997")
            assert loaded is not None
            assert loaded["ficha"] == "3388997"
            assert len(loaded["mappings"]) == 2

    def test_load_nonexistent(self, tmp_path):
        with patch("src.store.rap_mapping_store.RAP_MAPPINGS_DIR", tmp_path):
            result = load_rap_mapping("9999999")
            assert result is None

    def test_delete_existing(self, tmp_path):
        with patch("src.store.rap_mapping_store.RAP_MAPPINGS_DIR", tmp_path):
            save_rap_mapping("3388997", {**SAMPLE_MAPPING})
            assert delete_rap_mapping("3388997") is True
            assert load_rap_mapping("3388997") is None

    def test_delete_nonexistent(self, tmp_path):
        with patch("src.store.rap_mapping_store.RAP_MAPPINGS_DIR", tmp_path):
            assert delete_rap_mapping("9999999") is False

    def test_save_overwrites(self, tmp_path):
        with patch("src.store.rap_mapping_store.RAP_MAPPINGS_DIR", tmp_path):
            save_rap_mapping("3388997", {"mappings": [{"rap": "OLD"}], "stats": {}})
            save_rap_mapping("3388997", {**SAMPLE_MAPPING})
            loaded = load_rap_mapping("3388997")
            assert len(loaded["mappings"]) == 2

    def test_creates_directory(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        with patch("src.store.rap_mapping_store.RAP_MAPPINGS_DIR", nested):
            save_rap_mapping("3388997", {"mappings": [], "stats": {}})
            assert nested.exists()

    def test_file_content_is_valid_json(self, tmp_path):
        with patch("src.store.rap_mapping_store.RAP_MAPPINGS_DIR", tmp_path):
            save_rap_mapping("3388997", {**SAMPLE_MAPPING})
            # Guarda en la carpeta del instructor (el "1" de los tests)
            raw = (tmp_path / "1" / "3388997.json").read_text(encoding="utf-8")
            data = json.loads(raw)
            assert data["ficha"] == "3388997"
            assert "mappings" in data
