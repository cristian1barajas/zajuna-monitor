"""Tests for quiz index parser."""
from dataclasses import dataclass
from pathlib import Path

import pytest
from src.parsers.grader import ParseError
from src.parsers.quiz_index import (
    QuizEntry,
    match_quizzes_to_evidences,
    parse_quiz_index,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def index_html():
    """Load the quiz index HTML fixture."""
    path = FIXTURE_DIR / "quiz_index_sample.html"
    if not path.exists():
        pytest.skip("quiz_index_sample.html fixture not found")
    return path.read_text(encoding="utf-8")


@dataclass
class FakeEvidence:
    item_id: int
    name: str


# ─── Quiz Index Parser Tests ──────────────────────────────────────────────


class TestQuizIndexParser:
    def test_parses_all_quizzes(self, index_html):
        result = parse_quiz_index(index_html)
        assert len(result) == 3

    def test_extracts_cmids(self, index_html):
        result = parse_quiz_index(index_html)
        cmids = [q.cmid for q in result]
        assert 5967188 in cmids
        assert 5967240 in cmids
        assert 5967249 in cmids

    def test_extracts_names(self, index_html):
        result = parse_quiz_index(index_html)
        names = [q.name for q in result]
        assert "Cuestionario. GA1-240202501-AA1-EV01." in names
        assert "Cuestionario. GA2-240202501-AA1-EV01." in names

    def test_ignores_absolute_links(self, index_html):
        """Absolute links (course/view.php, user/view.php, forum/view.php) must NOT match."""
        result = parse_quiz_index(index_html)
        cmids = [q.cmid for q in result]
        # These are in the navbar as absolute URLs
        assert 89977 not in cmids   # course/view.php
        assert 718455 not in cmids  # user/view.php
        assert 26790 not in cmids   # forum/view.php

    def test_no_duplicates(self):
        """Duplicate links should be deduplicated by cmid."""
        html = '''<table class="generaltable">
            <tr><td><a href="view.php?id=100">Quiz A</a></td></tr>
            <tr><td><a href="view.php?id=100">Quiz A duplicate</a></td></tr>
            <tr><td><a href="view.php?id=200">Quiz B</a></td></tr>
        </table>'''
        result = parse_quiz_index(html)
        assert len(result) == 2

    def test_raises_on_empty_html(self):
        with pytest.raises(ParseError):
            parse_quiz_index("<html><body>No quizzes</body></html>")

    def test_raises_on_no_links(self):
        html = '<html><body><table class="generaltable"></table></body></html>'
        with pytest.raises(ParseError):
            parse_quiz_index(html)

    def test_raises_on_no_table(self):
        html = "<html><body><p>No table here</p></body></html>"
        with pytest.raises(ParseError):
            parse_quiz_index(html)

    def test_entry_dataclass(self):
        entry = QuizEntry(name="Test Quiz", cmid=123)
        assert entry.name == "Test Quiz"
        assert entry.cmid == 123


# ─── Quiz Matching Tests ─────────────────────────────────────────────────


class TestQuizMatching:
    def test_matches_by_exact_name(self):
        quizzes = [QuizEntry(name="Cuestionario. GA1-240202501-AA1-EV01.", cmid=100)]
        evidences = [FakeEvidence(item_id=999, name="Cuestionario. GA1-240202501-AA1-EV01.")]
        result = match_quizzes_to_evidences(quizzes, evidences)
        assert len(result) == 1
        assert result[0]["item_id"] == 999
        assert result[0]["module_type"] == "quiz"

    def test_matches_by_substring(self):
        quizzes = [QuizEntry(name="Cuestionario. GA1-240202501-AA1-EV01. calificación", cmid=100)]
        evidences = [FakeEvidence(item_id=999, name="Cuestionario. GA1-240202501-AA1-EV01.")]
        result = match_quizzes_to_evidences(quizzes, evidences)
        assert result[0]["item_id"] == 999

    def test_no_match_returns_none_item_id(self):
        quizzes = [QuizEntry(name="Unmatched Quiz", cmid=100)]
        evidences = [FakeEvidence(item_id=999, name="Completely different")]
        result = match_quizzes_to_evidences(quizzes, evidences)
        assert result[0]["item_id"] is None
        assert result[0]["module_type"] == "quiz"

    def test_all_entries_have_quiz_module_type(self):
        quizzes = [
            QuizEntry(name="Quiz A", cmid=100),
            QuizEntry(name="Quiz B", cmid=200),
        ]
        evidences = [FakeEvidence(item_id=1, name="Quiz A")]
        result = match_quizzes_to_evidences(quizzes, evidences)
        assert all(r["module_type"] == "quiz" for r in result)

    def test_matches_by_prefix(self):
        quizzes = [QuizEntry(
            name="Cuestionario sobre metodologías ágiles de desarrollo de software",
            cmid=100,
        )]
        evidences = [FakeEvidence(
            item_id=999,
            name="Cuestionario sobre metodologías ágiles de desarrollo de software avanzado",
        )]
        result = match_quizzes_to_evidences(quizzes, evidences)
        assert result[0]["item_id"] == 999

    def test_same_guide_aa1_and_aa2_do_not_collide(self):
        """AA1-EV01 and AA2-EV01 share a 30-char prefix; the GA code must decide."""
        quizzes = [
            QuizEntry(name="Cuestionario. GA2-240202501-AA1-EV01.", cmid=100),
            QuizEntry(name="Cuestionario. GA2-240202501-AA2-EV01.", cmid=200),
        ]
        evidences = [
            FakeEvidence(item_id=2503228, name="Cuestionario. GA2-240202501-AA1-EV01."),
            FakeEvidence(item_id=2503244, name="Cuestionario. GA2-240202501-AA2-EV01."),
        ]
        result = match_quizzes_to_evidences(quizzes, evidences)
        assert [r["item_id"] for r in result] == [2503228, 2503244]

    def test_matches_by_ga_code_despite_extra_spaces(self):
        quizzes = [QuizEntry(name="Cuestionario.  GA3-240202501-AA2-EV01.", cmid=200)]
        evidences = [
            FakeEvidence(item_id=2503325, name="Cuestionario.  GA3-240202501-AA1-EV01."),
            FakeEvidence(item_id=2503342, name="Cuestionario. GA3-240202501-AA2-EV01."),
        ]
        result = match_quizzes_to_evidences(quizzes, evidences)
        assert result[0]["item_id"] == 2503342

    def test_empty_quizzes(self):
        result = match_quizzes_to_evidences([], [FakeEvidence(item_id=1, name="X")])
        assert result == []

    def test_empty_evidences(self):
        quizzes = [QuizEntry(name="Quiz", cmid=100)]
        result = match_quizzes_to_evidences(quizzes, [])
        assert len(result) == 1
        assert result[0]["item_id"] is None
