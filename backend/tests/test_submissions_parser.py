"""Tests for the submissions list parser."""
from pathlib import Path

import pytest
from src.parsers.submissions_list import (
    SubmissionsPage,
    parse_instrument_url,
    parse_submissions_page,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def submissions_html() -> str:
    return (FIXTURES / "assignment_submissions_sample.html").read_text(encoding="utf-8")


@pytest.fixture
def instrument_html() -> str:
    return (FIXTURES / "assignment_detail_with_instrument.html").read_text(
        encoding="utf-8"
    )


class TestParseSubmissionsPage:
    def test_returns_submissions_page(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        assert isinstance(result, SubmissionsPage)
        assert result.cmid == 5967181

    def test_extracts_assignment_name(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        assert "GA1-220501046-AA2-EV01" in result.assignment_name

    def test_extracts_all_student_rows(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        # 6 students in fixture (ignoring ygtvrow auxiliary rows)
        assert len(result.entries) == 6

    def test_ignores_auxiliary_rows(self, submissions_html):
        """YUI tree rows (class=ygtvrow) must not be parsed as students."""
        result = parse_submissions_page(submissions_html, cmid=5967181)
        for entry in result.entries:
            assert entry.user_id != 0

    def test_extracts_student_name(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        names = [e.full_name for e in result.entries]
        assert "IRENE LUCIA PRUEBA NUEVE" in names
        assert "JORGE IVAN PRUEBA DIEZ" in names

    def test_extracts_document_without_suffix(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        docs = {e.full_name: e.document for e in result.entries}
        assert docs["IRENE LUCIA PRUEBA NUEVE"] == "1000000001"
        assert docs["JORGE IVAN PRUEBA DIEZ"] == "80000002"

    def test_extracts_email(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        emails = {e.full_name: e.email for e in result.entries}
        assert emails["IRENE LUCIA PRUEBA NUEVE"] == "aprendiz1@example.com"

    def test_status_submitted_and_graded(self, submissions_html):
        """Student 1: Submitted + Graded."""
        result = parse_submissions_page(submissions_html, cmid=5967181)
        karen = next(e for e in result.entries if e.user_id == 781585)
        assert karen.status == "Enviado para calificar"
        assert karen.is_graded is True

    def test_status_sin_entrega(self, submissions_html):
        """Student 4: Sin entrega."""
        result = parse_submissions_page(submissions_html, cmid=5967181)
        juan = next(e for e in result.entries if e.user_id == 23927)
        assert juan.status == "Sin entrega"
        assert juan.is_graded is False
        assert juan.file_urls == []
        assert juan.file_names == []

    def test_status_submitted_pending_grading(self, submissions_html):
        """Student 5: Submitted but NOT graded yet."""
        result = parse_submissions_page(submissions_html, cmid=5967181)
        carlos = next(e for e in result.entries if e.user_id == 900100)
        assert carlos.status == "Enviado para calificar"
        assert carlos.is_graded is False
        assert len(carlos.file_urls) == 1

    def test_extracts_file_urls(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        karen = next(e for e in result.entries if e.user_id == 781585)
        assert len(karen.file_urls) == 1
        assert "pluginfile" in karen.file_urls[0]
        assert "781585" in karen.file_urls[0]

    def test_extracts_file_names(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        karen = next(e for e in result.entries if e.user_id == 781585)
        assert karen.file_names == ["Utilizacion_herramientas_ofimatica.pdf"]

    def test_multiple_files_per_student(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        jorge = next(e for e in result.entries if e.user_id == 821571)
        assert len(jorge.file_urls) == 2
        assert len(jorge.file_names) == 2
        assert "Parte1.docx" in jorge.file_names[0]
        assert "Parte2.pdf" in jorge.file_names[1]

    def test_no_files_for_sin_entrega(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        juan = next(e for e in result.entries if e.user_id == 23927)
        assert juan.file_urls == []
        assert juan.file_names == []

    def test_last_modified_present(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        karen = next(e for e in result.entries if e.user_id == 781585)
        assert karen.last_modified is not None
        assert "marzo" in karen.last_modified

    def test_last_modified_none_for_no_submission(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        juan = next(e for e in result.entries if e.user_id == 23927)
        assert juan.last_modified is None

    def test_unique_statuses(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        statuses = result.statuses
        assert "Enviado para calificar" in statuses
        assert "Sin entrega" in statuses

    def test_empty_html_returns_empty(self):
        result = parse_submissions_page("<html><body></body></html>", cmid=999)
        assert result.cmid == 999
        assert result.entries == []

    def test_user_id_extraction(self, submissions_html):
        result = parse_submissions_page(submissions_html, cmid=5967181)
        user_ids = [e.user_id for e in result.entries]
        assert 781585 in user_ids
        assert 821571 in user_ids
        assert 23927 in user_ids
        assert 900100 in user_ids


class TestParseInstrumentUrl:
    def test_extracts_instrument_url(self, instrument_html):
        url, name = parse_instrument_url(instrument_html)
        assert url is not None
        assert "IE-GA1-220501046-AA2-EV01.pdf" in url

    def test_extracts_instrument_name(self, instrument_html):
        url, name = parse_instrument_url(instrument_html)
        assert name == "IE-GA1-220501046-AA2-EV01.pdf"

    def test_no_instrument_returns_none(self):
        url, name = parse_instrument_url("<html><body></body></html>")
        assert url is None
        assert name is None

    def test_instrument_from_submissions_page_without_buttons(self, submissions_html):
        """The grading page may not have instrument buttons."""
        url, name = parse_instrument_url(submissions_html)
        # The submissions fixture doesn't have instrument buttons
        assert url is None
