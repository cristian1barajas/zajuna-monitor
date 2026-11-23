"""Tests for GraderParser against fixture HTML."""
from pathlib import Path

import pytest
from src.models.schemas import GradeStatus
from src.parsers.grader import GraderParser, ParseError

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def grader_html():
    """Load the grader report HTML fixture."""
    fixture_path = FIXTURE_DIR / "grader_sample.html"
    if not fixture_path.exists():
        pytest.skip("grader_sample.html fixture not found")
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def parser(grader_html):
    return GraderParser(grader_html, course_id=89977)


@pytest.fixture
def report(parser):
    return parser.parse()


class TestCourseInfo:
    def test_extracts_course_name(self, report):
        assert "ANALISIS Y DESARROLLO DE SOFTWARE" in report.course_name

    def test_extracts_ficha(self, report):
        assert report.ficha == "3388997"

    def test_course_id_matches(self, report):
        assert report.course_id == 89977


class TestEvidenceHeaders:
    def test_evidence_count(self, report):
        assert len(report.evidences) == 194

    def test_first_evidence_has_item_id(self, report):
        assert report.evidences[0].item_id == 2506476

    def test_first_evidence_has_name(self, report):
        assert "sistemas" in report.evidences[0].name.lower()

    def test_evidence_has_category(self, report):
        first = report.evidences[0]
        assert first.category != ""
        assert "Fase 1" in first.category or "lisis" in first.category

    def test_no_category_totals_in_evidences(self, report):
        """categoryitem headers should NOT appear as evidences."""
        for ev in report.evidences:
            assert ev.name != ""
            assert "Total" not in ev.name or "total" not in ev.name.lower()

    def test_all_evidences_have_unique_ids(self, report):
        ids = [e.item_id for e in report.evidences]
        assert len(ids) == len(set(ids))


class TestStudentRows:
    def test_student_count(self, report):
        assert len(report.students) == 44

    def test_first_student_user_id(self, report):
        assert report.students[0].user_id == 2254444

    def test_first_student_name(self, report):
        first = report.students[0]
        assert "ALBERTO" in first.full_name
        assert "ARANDIA" in first.full_name

    def test_name_has_no_extra_whitespace(self, report):
        for student in report.students:
            assert "  " not in student.full_name
            assert "\n" not in student.full_name

    def test_document_stripped_of_suffix(self, report):
        first = report.students[0]
        assert first.document == "1000000007"
        assert not first.document.endswith("cc")

    def test_all_students_have_documents(self, report):
        for student in report.students:
            assert student.document != ""
            assert student.document.isdigit()

    def test_all_students_have_email(self, report):
        for student in report.students:
            assert "@" in student.email

    def test_each_student_has_all_grades(self, report):
        for student in report.students:
            assert len(student.grades) == len(report.evidences)


class TestGradeValues:
    def test_grade_values_are_valid(self, report):
        valid = {GradeStatus.APPROVED, GradeStatus.DISAPPROVED, GradeStatus.PENDING}
        for student in report.students:
            for grade in student.grades.values():
                assert grade.value in valid

    def test_approved_has_passed_true(self, report):
        for student in report.students:
            for grade in student.grades.values():
                if grade.value == GradeStatus.APPROVED:
                    assert grade.passed is True

    def test_pending_has_passed_false(self, report):
        for student in report.students:
            for grade in student.grades.values():
                if grade.value == GradeStatus.PENDING:
                    assert grade.passed is False

    def test_total_grades_match(self, report):
        """Total grade cells = students x evidences."""
        total = sum(len(s.grades) for s in report.students)
        assert total == len(report.students) * len(report.evidences)


class TestSummary:
    def test_summary_totals(self, parser, report):
        summary = parser.compute_summary(report)
        assert summary.total_students == 44
        assert summary.total_evidences == 194
        total = summary.total_approved + summary.total_disapproved + summary.total_pending
        assert total == 44 * 194

    def test_completion_percentage_range(self, parser, report):
        summary = parser.compute_summary(report)
        assert 0 <= summary.completion_percentage <= 100

    def test_pending_by_evidence_keys(self, parser, report):
        summary = parser.compute_summary(report)
        assert len(summary.pending_by_evidence) == len(report.evidences)

    def test_summary_ficha(self, parser, report):
        summary = parser.compute_summary(report)
        assert summary.ficha == "3388997"


class TestParseError:
    def test_raises_on_missing_table(self):
        parser = GraderParser("<html><body>No table</body></html>", 99999)
        with pytest.raises(ParseError, match="Table #user-grades not found"):
            parser.parse()

    def test_raises_on_missing_title(self):
        html = '<html><body><table id="user-grades"></table></body></html>'
        parser = GraderParser(html, 99999)
        with pytest.raises(ParseError, match="No <title> tag found"):
            parser.parse()
