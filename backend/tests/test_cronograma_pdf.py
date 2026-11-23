"""Cronograma en PDF: lectura de la tabla y vista previa por API."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_snapshot
from src.api.server import app
from src.parsers.cronograma_pdf import (
    CronogramaPdfError,
    entries_from_rows,
    extract_rows,
    parse_spanish_date,
)

FICHA = "3389000"


def _row(evidence: str, start: str, end: str, ficha: str | None = FICHA) -> list[str | None]:
    """Fila como la entrega pdfplumber: 11 columnas, celdas con saltos de línea."""
    return [
        None, ficha, "PLANEACIÓN", "AP5. Construir el prototipo",
        "220501095. Diseñar la solución", "220501095-03. Determinar",
        evidence, "16", start, end, "Christian Barajas",
    ]


OCT_28 = "Miércoles, 28 de\noctubre de 2026"
OCT_22 = "Jueves, 22 de\noctubre de 2026"


class TestParseSpanishDate:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Miércoles, 28 de octubre de 2026", "2026-10-28"),
            ("Lunes, 9 de\nnoviembre de 2026", "2026-11-09"),
            ("Martes, 1 de Setiembre de 2026", "2026-09-01"),
        ],
    )
    def test_reads_written_dates(self, text, expected):
        assert parse_spanish_date(text) == expected

    def test_unknown_text(self):
        assert parse_spanish_date("Christian Barajas") is None


class TestEntriesFromRows:
    def test_code_split_across_lines(self):
        rows = [_row("Evidencia de producto: Maquetación en HTML. GA5-220501095-AA1-\nEV04.", OCT_22, OCT_28)]
        entries, warnings, fichas = entries_from_rows(rows)
        assert entries == [{"evidence_name": "GA5-220501095-AA1-EV04", "cutoff_date": "2026-10-28"}]
        assert warnings == []
        assert fichas == {FICHA}

    def test_cutoff_is_the_final_date(self):
        rows = [_row("Blog. GA4-240202501-AA1-EV03.", "Jueves, 15 de octubre de 2026", OCT_28)]
        entries, _, _ = entries_from_rows(rows)
        assert entries[0]["cutoff_date"] == "2026-10-28"

    def test_repeated_evidence_keeps_latest_date(self):
        rows = [
            _row("Video. GA3-240202501-AA2-EV01.", "x", "Martes, 28 de julio de 2026"),
            _row("Video. GA3-240202501-AA2-EV01.", "x", "Martes, 11 de agosto de 2026"),
        ]
        entries, _, _ = entries_from_rows(rows)
        assert entries == [{"evidence_name": "GA3-240202501-AA2-EV01", "cutoff_date": "2026-08-11"}]

    def test_several_codes_in_one_cell_share_the_date(self):
        rows = [_row("Evidencias: GA5-240201064-AA2-EV01 y GA5-240201064-AA2-EV02.", "x", OCT_28)]
        entries, _, _ = entries_from_rows(rows)
        assert [e["evidence_name"] for e in entries] == [
            "GA5-240201064-AA2-EV01",
            "GA5-240201064-AA2-EV02",
        ]

    def test_blank_rows_and_week_labels_are_ignored(self):
        rows = [["1 anameS", "", "", "", "", "", "", "", "", "", ""], [""] * 11]
        assert entries_from_rows(rows) == ([], [], set())

    def test_evidence_without_code_is_reported(self):
        rows = [_row("Evidencia de producto: Mapa mental sin código", "x", OCT_28)]
        entries, warnings, _ = entries_from_rows(rows)
        assert entries == []
        assert len(warnings) == 1
        assert "sin código" in warnings[0]

    def test_evidence_without_date_is_reported(self):
        rows = [_row("Taller. GA5-220501095-AA1-EV01.", "", "")]
        entries, warnings, _ = entries_from_rows(rows)
        assert entries == []
        assert warnings == ["GA5-220501095-AA1-EV01 no trae fecha final"]

    def test_sorted_by_date(self):
        rows = [
            _row("GA5-220501095-AA1-EV05.", "x", OCT_28),
            _row("GA4-220501095-AA4-EV01.", "x", "Miércoles, 7 de octubre de 2026"),
        ]
        entries, _, _ = entries_from_rows(rows)
        assert [e["cutoff_date"] for e in entries] == ["2026-10-07", "2026-10-28"]


class TestExtractRows:
    def test_rejects_files_that_are_not_pdf(self):
        with pytest.raises(CronogramaPdfError):
            extract_rows(b"evidencia,fecha\nGA1,2026-01-01")

    def test_rejects_broken_pdf(self):
        with pytest.raises(CronogramaPdfError):
            extract_rows(b"%PDF-1.7 esto no es un pdf completo")


SNAPSHOT = {
    "courses": [
        {
            "course_id": 1,
            "ficha": FICHA,
            "evidences": [
                {"item_id": 501, "name": "Maquetación de la interfaz gráfica en HTML. GA5-220501095-AA1-EV04."},
            ],
        }
    ],
    "summaries": [],
    "participants": [],
}

PARSED = {
    b"%PDF-oct": (
        [
            {"evidence_name": "GA5-220501095-AA1-EV04", "cutoff_date": "2026-10-28"},
            {"evidence_name": "GA3-240202501-AA2-EV01", "cutoff_date": "2026-07-28"},
        ],
        [],
        {FICHA},
    ),
    b"%PDF-ago": (
        [{"evidence_name": "GA3-240202501-AA2-EV01", "cutoff_date": "2026-08-11"}],
        ["Fila sin código de evidencia: «Evidencia de producto: Mapa»"],
        {FICHA},
    ),
    b"%PDF-otra": (
        [{"evidence_name": "GA1-220501092-AA1-EV01", "cutoff_date": "2026-02-15"}],
        [],
        {"2977397"},
    ),
}


def _fake_parse(content: bytes):
    if content not in PARSED:
        raise CronogramaPdfError("no es un PDF")
    return PARSED[content]


@pytest.fixture
def client():
    app.dependency_overrides[get_snapshot] = lambda: SNAPSHOT
    with (
        patch("src.api.routes.cronograma.parse_cronograma_pdf", side_effect=_fake_parse),
        TestClient(app) as c,
    ):
        yield c
    app.dependency_overrides.clear()


def _upload(client, *files: tuple[str, bytes]):
    return client.post(
        f"/api/cronograma/{FICHA}/pdf",
        files=[("files", (name, content, "application/pdf")) for name, content in files],
    )


class TestPreviewEndpoint:
    def test_merges_months_and_links_evidences(self, client):
        resp = _upload(client, ("10 Octubre.pdf", b"%PDF-oct"), ("08 Agosto.pdf", b"%PDF-ago"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries"] == [
            {"evidence_name": "GA3-240202501-AA2-EV01", "evidence_item_id": None, "cutoff_date": "2026-08-11"},
            {"evidence_name": "GA5-220501095-AA1-EV04", "evidence_item_id": 501, "cutoff_date": "2026-10-28"},
        ]
        assert data["files"] == [
            {"filename": "10 Octubre.pdf", "entries": 2},
            {"filename": "08 Agosto.pdf", "entries": 1},
        ]
        assert data["warnings"] == ["08 Agosto.pdf: Fila sin código de evidencia: «Evidencia de producto: Mapa»"]

    def test_does_not_save(self, client, tmp_path):
        with patch("src.store.cronograma_store.CRONOGRAMAS_DIR", tmp_path):
            _upload(client, ("10 Octubre.pdf", b"%PDF-oct"))
        assert list(tmp_path.iterdir()) == []

    def test_skips_pdf_of_another_ficha(self, client):
        resp = _upload(client, ("10 Octubre.pdf", b"%PDF-oct"), ("otra.pdf", b"%PDF-otra"))
        data = resp.json()
        assert "GA1-220501092-AA1-EV01" not in [e["evidence_name"] for e in data["entries"]]
        assert any("es de la ficha 2977397" in w for w in data["warnings"])

    def test_unreadable_file_is_a_warning_when_others_work(self, client):
        resp = _upload(client, ("10 Octubre.pdf", b"%PDF-oct"), ("notas.txt", b"hola"))
        assert resp.status_code == 200
        assert resp.json()["warnings"] == ["notas.txt: no es un PDF"]

    def test_nothing_readable_is_an_error(self, client):
        resp = _upload(client, ("notas.txt", b"hola"))
        assert resp.status_code == 422
        assert "notas.txt: no es un PDF" in resp.json()["detail"]
