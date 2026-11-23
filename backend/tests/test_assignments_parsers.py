"""Tests for assignments index and assignment detail parsers."""
from pathlib import Path

import pytest
from src.parsers.assignment_detail import (
    AssignmentGradingInfo,
    parse_assignment_detail,
)
from src.parsers.assignments_index import (
    AssignmentEntry,
    match_assignments_to_evidences,
    parse_assignments_index,
)
from src.parsers.grader import ParseError

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def index_html():
    """Load the assignments index HTML fixture."""
    path = FIXTURE_DIR / "assignments_index_sample.html"
    if not path.exists():
        pytest.skip("assignments_index_sample.html fixture not found")
    return path.read_text(encoding="utf-8")


@pytest.fixture
def detail_html():
    """Load the assignment detail HTML fixture."""
    path = FIXTURE_DIR / "assignment_detail_sample.html"
    if not path.exists():
        pytest.skip("assignment_detail_sample.html fixture not found")
    return path.read_text(encoding="utf-8")


# ─── Assignments Index Parser Tests ───────────────────────────────────────


class TestAssignmentsIndexParser:
    def test_parses_all_assignments(self, index_html):
        result = parse_assignments_index(index_html)
        assert len(result) == 5

    def test_extracts_cmids(self, index_html):
        result = parse_assignments_index(index_html)
        cmids = [a.cmid for a in result]
        assert 1343194 in cmids
        assert 1343195 in cmids
        assert 1343196 in cmids
        assert 1343200 in cmids
        assert 1343201 in cmids

    def test_extracts_names(self, index_html):
        result = parse_assignments_index(index_html)
        names = [a.name for a in result]
        assert any("GA1-220501092-AA1-EV01" in n for n in names)
        assert any("Diagrama de clases" in n for n in names)

    def test_first_assignment(self, index_html):
        result = parse_assignments_index(index_html)
        first = result[0]
        assert first.cmid == 1343194
        assert "GA1-220501092-AA1-EV01" in first.name
        assert "Infografia" in first.name

    def test_returns_assignment_entry_dataclass(self, index_html):
        result = parse_assignments_index(index_html)
        assert all(isinstance(a, AssignmentEntry) for a in result)

    def test_no_duplicate_cmids(self, index_html):
        result = parse_assignments_index(index_html)
        cmids = [a.cmid for a in result]
        assert len(cmids) == len(set(cmids))

    def test_empty_html_raises_parse_error(self):
        with pytest.raises(ParseError):
            parse_assignments_index("<html><body></body></html>")

    def test_html_with_duplicate_links_deduplicates(self):
        html = """
        <html><body>
            <a href="/zajuna/mod/assign/view.php?id=100">Task A</a>
            <a href="/zajuna/mod/assign/view.php?id=100">Task A (duplicate)</a>
            <a href="/zajuna/mod/assign/view.php?id=200">Task B</a>
        </body></html>
        """
        result = parse_assignments_index(html)
        assert len(result) == 2
        cmids = [a.cmid for a in result]
        assert cmids == [100, 200]


# ─── Assignment Detail Parser Tests ──────────────────────────────────────


class TestAssignmentDetailParser:
    def test_extracts_participants(self, detail_html):
        info = parse_assignment_detail(detail_html, cmid=1343194)
        assert info.participants == 44

    def test_extracts_drafts(self, detail_html):
        info = parse_assignment_detail(detail_html, cmid=1343194)
        assert info.drafts == 2

    def test_extracts_submitted(self, detail_html):
        info = parse_assignment_detail(detail_html, cmid=1343194)
        assert info.submitted == 35

    def test_extracts_needs_grading(self, detail_html):
        info = parse_assignment_detail(detail_html, cmid=1343194)
        assert info.needs_grading == 12

    def test_extracts_time_remaining(self, detail_html):
        info = parse_assignment_detail(detail_html, cmid=1343194)
        assert info.time_remaining is not None
        assert "vencido" in info.time_remaining

    def test_cmid_is_set(self, detail_html):
        info = parse_assignment_detail(detail_html, cmid=1343194)
        assert info.cmid == 1343194

    def test_returns_grading_info_dataclass(self, detail_html):
        info = parse_assignment_detail(detail_html, cmid=1343194)
        assert isinstance(info, AssignmentGradingInfo)

    def test_empty_html_returns_zeros(self):
        """When no grading summary is found, return zeros instead of raising."""
        info = parse_assignment_detail("<html><body></body></html>", cmid=999)
        assert info.cmid == 999
        assert info.participants == 0
        assert info.submitted == 0
        assert info.needs_grading == 0

    def test_zero_pending(self):
        html = """
        <html><body>
        <table class="generaltable">
            <tr><td>Participantes</td><td>44</td></tr>
            <tr><td>Borradores</td><td>0</td></tr>
            <tr><td>Enviados</td><td>44</td></tr>
            <tr><td>Pendientes por calificar</td><td>0</td></tr>
        </table>
        </body></html>
        """
        info = parse_assignment_detail(html, cmid=100)
        assert info.needs_grading == 0
        assert info.submitted == 44
        assert info.participants == 44


# ─── Assignment Matching Tests ───────────────────────────────────────────


class FakeEvidence:
    """Lightweight evidence stand-in for matching tests."""

    def __init__(self, item_id: int, name: str):
        self.item_id = item_id
        self.name = name


class TestMatchAssignmentsToEvidences:
    def test_exact_match(self):
        assignments = [
            AssignmentEntry(name="GA1-220501092-AA1-EV01 Infografia requisitos", cmid=100),
        ]
        evidences = [
            FakeEvidence(item_id=2506476, name="GA1-220501092-AA1-EV01 Infografia requisitos"),
        ]
        result = match_assignments_to_evidences(assignments, evidences)
        assert len(result) == 1
        assert result[0]["item_id"] == 2506476
        assert result[0]["cmid"] == 100

    def test_substring_match(self):
        assignments = [
            AssignmentEntry(
                name="GA1-220501092-AA1-EV01 Infografia requisitos del cliente para el proyecto",
                cmid=100,
            ),
        ]
        evidences = [
            FakeEvidence(
                item_id=2506476,
                name="GA1-220501092-AA1-EV01 Infografia requisitos del cliente",
            ),
        ]
        result = match_assignments_to_evidences(assignments, evidences)
        assert result[0]["item_id"] == 2506476

    def test_no_match_returns_none(self):
        assignments = [
            AssignmentEntry(name="Totally different assignment", cmid=100),
        ]
        evidences = [
            FakeEvidence(item_id=2506476, name="GA1-220501092-AA1-EV01 Infografia"),
        ]
        result = match_assignments_to_evidences(assignments, evidences)
        assert result[0]["item_id"] is None

    def test_multiple_assignments_mixed_matches(self):
        assignments = [
            AssignmentEntry(name="GA1-220501092-AA1-EV01 Infografia requisitos", cmid=100),
            AssignmentEntry(name="Tarea no relacionada", cmid=200),
            AssignmentEntry(name="GA2-220501093-AA1-EV01 Diagrama de clases", cmid=300),
        ]
        evidences = [
            FakeEvidence(item_id=1001, name="GA1-220501092-AA1-EV01 Infografia requisitos"),
            FakeEvidence(item_id=1002, name="GA2-220501093-AA1-EV01 Diagrama de clases"),
        ]
        result = match_assignments_to_evidences(assignments, evidences)
        assert result[0]["item_id"] == 1001
        assert result[1]["item_id"] is None
        assert result[2]["item_id"] == 1002

    def test_case_insensitive_matching(self):
        assignments = [
            AssignmentEntry(name="GA1-220501092-AA1-EV01 INFOGRAFIA REQUISITOS", cmid=100),
        ]
        evidences = [
            FakeEvidence(item_id=2506476, name="GA1-220501092-AA1-EV01 Infografia requisitos"),
        ]
        result = match_assignments_to_evidences(assignments, evidences)
        assert result[0]["item_id"] == 2506476

    def test_ga_code_prevents_false_match_similar_names(self):
        """Regression: assignments with similar names but different GA codes must NOT cross-match.

        Real bug: EV01 "caso" and EV03 "proyecto" share a >30 char prefix.
        Without GA code matching, both matched to EV01 item_id.
        """
        assignments = [
            AssignmentEntry(
                name="Diseño y Desarrollo de servicios web - caso GA7-220501096-AA5-EV01",
                cmid=1335868,
            ),
            AssignmentEntry(
                name="Diseño y Desarrollo de servicios web - proyecto GA7-220501096-AA5-EV03",
                cmid=1335870,
            ),
        ]
        evidences = [
            FakeEvidence(
                item_id=751769,
                name="Diseño y Desarrollo de servicios web - caso GA7-220501096-AA5-EV01",
            ),
            FakeEvidence(
                item_id=751771,
                name="Diseño y Desarrollo de servicios web - proyecto GA7-220501096-AA5-EV03",
            ),
        ]
        result = match_assignments_to_evidences(assignments, evidences)

        ev01 = next(r for r in result if r["cmid"] == 1335868)
        ev03 = next(r for r in result if r["cmid"] == 1335870)

        assert ev01["item_id"] == 751769, "EV01 should map to 751769"
        assert ev03["item_id"] == 751771, "EV03 should map to 751771 (NOT 751769)"

    def test_ga_code_prevents_false_match_different_aa(self):
        """Assignments with same description but different AA numbers must not cross-match."""
        assignments = [
            AssignmentEntry(
                name="Video-expositivo sobre experimento GA3-220201501-AA2-EV01",
                cmid=100,
            ),
            AssignmentEntry(
                name="Video-expositivo sobre experimento GA3-220201501-AA4-EV01",
                cmid=200,
            ),
        ]
        evidences = [
            FakeEvidence(item_id=1001, name="Video-expositivo sobre experimento GA3-220201501-AA2-EV01"),
            FakeEvidence(item_id=1002, name="Video-expositivo sobre experimento GA3-220201501-AA4-EV01"),
        ]
        result = match_assignments_to_evidences(assignments, evidences)

        r1 = next(r for r in result if r["cmid"] == 100)
        r2 = next(r for r in result if r["cmid"] == 200)

        assert r1["item_id"] == 1001, "AA2-EV01 should map to 1001"
        assert r2["item_id"] == 1002, "AA4-EV01 should map to 1002"
