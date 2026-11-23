"""Tests del parser del bloque "Mis cursos" de /zajuna/my/."""
from __future__ import annotations

from pathlib import Path

import pytest
from src.parsers.my_courses import parse_my_courses

FIXTURES = Path(__file__).parent / "fixtures"
REAL_SAMPLE = (
    Path(__file__).resolve().parents[2] / "docs" / "html-samples" / "html_que_devuelve_el_login.html"
)


@pytest.fixture
def result():
    html = (FIXTURES / "my_courses_nav_sample.html").read_text(encoding="utf-8")
    return parse_my_courses(html)


def _by_id(result, course_id):
    return next(c for c in result.courses if c.course_id == course_id)


class TestParseMyCourses:
    def test_dedupes_courses_by_id(self, result):
        ids = [c.course_id for c in result.courses]
        assert sorted(ids) == [90001, 90002, 90003, 90004]

    def test_standard_shortname_gives_program_and_ficha(self, result):
        adso = _by_id(result, 90001)
        assert adso.ficha == "1111111"
        assert adso.program_code == "228118"
        assert adso.shortname == "P_228118_V_1111111_R_11_C_9214"
        assert adso.fullname == "ANALISIS Y DESARROLLO DE SOFTWARE"

    def test_tps_program_fullname_is_cleaned(self, result):
        tps = _by_id(result, 90002)
        assert tps.program_code == "233104"
        assert tps.ficha == "2222222"
        assert tps.fullname == "PROGRAMACION DE SOFTWARE"

    def test_nonstandard_shortname_falls_back_to_title_ficha(self, result):
        course = _by_id(result, 90003)
        assert course.ficha == "3333333"
        assert course.program_code == ""
        assert course.fullname == "CURSO COMPLEMENTARIO"

    def test_course_without_ficha_is_kept_with_empty_ficha(self, result):
        course = _by_id(result, 90004)
        assert course.ficha == ""
        assert course.fullname == "ESPACIO DE INSTRUCTORES"

    def test_more_link_marks_result_as_truncated(self, result):
        assert result.truncated is True

    def test_page_without_course_block_returns_empty(self):
        empty = parse_my_courses("<html><body><p>Hola</p></body></html>")
        assert empty.courses == []
        assert empty.truncated is False


@pytest.mark.skipif(not REAL_SAMPLE.exists(), reason="muestra real de /my/ no disponible")
def test_real_my_page_sample():
    result = parse_my_courses(REAL_SAMPLE.read_text(encoding="utf-8"))
    by_ficha = {c.ficha: c for c in result.courses}
    assert len(result.courses) == 8
    assert by_ficha["3388997"].course_id == 89977
    assert by_ficha["3388997"].program_code == "228118"
    assert by_ficha["3118277"].program_code == "233104"
    assert result.truncated is False
