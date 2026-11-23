"""Unit tests for parse_last_access_to_days function."""

from src.parsers.participants import parse_last_access_to_days


class TestLastAccessParsing:
    """Test all known formats of Spanish relative time strings."""

    def test_seconds(self):
        assert parse_last_access_to_days("8 segundos") == 0

    def test_minutes(self):
        assert parse_last_access_to_days("45 minutos") == 0

    def test_hours_and_minutes(self):
        assert parse_last_access_to_days("13 horas 58 minutos") == 0

    def test_hours_only(self):
        assert parse_last_access_to_days("22 horas") == 0

    def test_days_and_hours(self):
        assert parse_last_access_to_days("12 días 17 horas") == 12

    def test_days_only(self):
        assert parse_last_access_to_days("47 días") == 47

    def test_many_days_and_hours(self):
        assert parse_last_access_to_days("333 días 7 horas") == 333

    def test_year_and_days(self):
        assert parse_last_access_to_days("1 año 171 días") == 536

    def test_nunca(self):
        assert parse_last_access_to_days("Nunca") == 9999

    def test_ahora(self):
        assert parse_last_access_to_days("ahora") == 0

    def test_empty_string(self):
        assert parse_last_access_to_days("") == -1

    def test_whitespace_only(self):
        assert parse_last_access_to_days("   ") == -1

    def test_one_day(self):
        assert parse_last_access_to_days("1 día") == 1

    def test_one_minute(self):
        assert parse_last_access_to_days("1 minuto") == 0

    def test_one_hour(self):
        assert parse_last_access_to_days("1 hora") == 0

    def test_days_without_accent(self):
        """Sometimes Moodle strips accents."""
        assert parse_last_access_to_days("12 dias 17 horas") == 12

    def test_year_without_accent(self):
        assert parse_last_access_to_days("1 ano 171 dias") == 536

    def test_months(self):
        assert parse_last_access_to_days("2 meses 15 días") == 75

    def test_one_month(self):
        assert parse_last_access_to_days("1 mes") == 30

    def test_nunca_lowercase(self):
        assert parse_last_access_to_days("nunca") == 9999

    def test_5_days_2_hours(self):
        assert parse_last_access_to_days("5 días 2 horas") == 5

    def test_34_days_16_hours(self):
        assert parse_last_access_to_days("34 días 16 horas") == 34
