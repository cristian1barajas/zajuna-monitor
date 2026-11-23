"""Tests for ParticipantsParser against fixture HTML."""
from pathlib import Path

import pytest
from src.models.schemas import StudentStatus
from src.parsers.participants import ParseError, ParticipantsParser

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def participants_html():
    """Load the participants page HTML fixture."""
    fixture_path = FIXTURE_DIR / "participants_sample.html"
    if not fixture_path.exists():
        pytest.skip("participants_sample.html fixture not found")
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def parser(participants_html):
    return ParticipantsParser(participants_html, course_id=89977)


@pytest.fixture
def result(parser):
    return parser.parse()


class TestCourseInfo:
    def test_extracts_ficha(self, result):
        assert result.ficha == "3388997"

    def test_course_id_matches(self, result):
        assert result.course_id == 89977


class TestParticipantFiltering:
    def test_only_aprendiz_included(self, result):
        """Should exclude Instructor and Acompañamiento roles."""
        roles = {p.role for p in result.participants}
        assert roles == {"Aprendiz"}

    def test_correct_count(self, result):
        """Fixture has 7 Aprendiz + 1 Instructor + 1 Acompañamiento + 1 empty."""
        assert len(result.participants) == 7

    def test_instructor_excluded(self, result):
        """Instructor (user 718455) should not be in the list."""
        user_ids = {p.user_id for p in result.participants}
        assert 718455 not in user_ids

    def test_empty_rows_excluded(self, result):
        """Empty ghost rows should be skipped."""
        for p in result.participants:
            assert p.full_name != ""
            assert p.document != ""


class TestParticipantData:
    def test_first_participant_name(self, result):
        p = result.participants[0]
        assert p.full_name == "JUAN CARLOS GARCIA LOPEZ"

    def test_first_participant_user_id(self, result):
        p = result.participants[0]
        assert p.user_id == 100001

    def test_first_participant_document(self, result):
        """Document suffix 'cc' should be stripped."""
        p = result.participants[0]
        assert p.document == "1000000007"

    def test_document_suffix_ti_stripped(self, result):
        """Document suffix 'TI' should also be stripped."""
        pedro = next(p for p in result.participants if p.user_id == 100003)
        assert pedro.document == "1007936702"

    def test_email_extraction(self, result):
        p = result.participants[0]
        assert p.email == "juangarcia@email.com"

    def test_groups_extraction(self, result):
        pedro = next(p for p in result.participants if p.user_id == 100003)
        assert pedro.groups == "Grupo A"

    def test_groups_no_hay(self, result):
        p = result.participants[0]
        assert p.groups == "No hay grupos"


class TestStatus:
    def test_active_status(self, result):
        p = result.participants[0]
        assert p.status == StudentStatus.ACTIVE

    def test_suspended_status(self, result):
        pedro = next(p for p in result.participants if p.user_id == 100003)
        assert pedro.status == StudentStatus.SUSPENDED

    def test_active_count(self, result):
        active = [p for p in result.participants if p.status == StudentStatus.ACTIVE]
        assert len(active) == 5

    def test_suspended_count(self, result):
        suspended = [p for p in result.participants if p.status == StudentStatus.SUSPENDED]
        assert len(suspended) == 2


class TestLastAccess:
    def test_days_and_hours(self, result):
        """'12 días 17 horas' -> 12 days."""
        p = result.participants[0]
        assert p.last_access_days == 12
        assert "12" in p.last_access_raw

    def test_hours_and_minutes(self, result):
        """'13 horas 58 minutos' -> 0 days."""
        valentina = next(p for p in result.participants if p.user_id == 100002)
        assert valentina.last_access_days == 0

    def test_days_only(self, result):
        """'47 días' -> 47 days."""
        pedro = next(p for p in result.participants if p.user_id == 100003)
        assert pedro.last_access_days == 47

    def test_nunca(self, result):
        """'Nunca' -> 9999 days."""
        laura = next(p for p in result.participants if p.user_id == 100004)
        assert laura.last_access_days == 9999

    def test_year_and_days(self, result):
        """'1 año 171 días' -> 536 days (365+171)."""
        andres = next(p for p in result.participants if p.user_id == 100005)
        assert andres.last_access_days == 536

    def test_ahora(self, result):
        """'ahora' -> 0 days."""
        daniela = next(p for p in result.participants if p.user_id == 100006)
        assert daniela.last_access_days == 0

    def test_many_days_and_hours(self, result):
        """'333 días 7 horas' -> 333 days."""
        santiago = next(p for p in result.participants if p.user_id == 100007)
        assert santiago.last_access_days == 333


class TestErrorHandling:
    def test_missing_table_raises_error(self):
        html = "<html><body><p>No table here</p></body></html>"
        parser = ParticipantsParser(html, course_id=99999)
        with pytest.raises(ParseError, match="Table #participants not found"):
            parser.parse()
