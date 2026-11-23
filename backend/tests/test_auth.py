"""Tests for AuthManager, focused on parsing logic (no network calls)."""
from unittest.mock import MagicMock

import pytest
from src.auth.manager import FIELD_PATTERN, MCFG_PATTERN, AuthError, AuthManager

# Sample HTML from the Zajuna wrapper response (based on real Postman capture)
SAMPLE_WRAPPER_HTML = """
    <script type='text/javascript'>
        function enviarForm(){
            document.getElementById('loginForm').submit();
        }
        enviarForm()
    </script>
    <body onLoad='enviarForm();'>
        <form style='display:none;' id='loginForm'
              action='/zajuna/login/index.php' class='form'
              method='POST' autocomplete='nop'>
            <input type='hidden' name='josso' value='8teq07JHYfXpjPsF/HHtCQ=='>
            <input type='hidden' name='logintoken' value='Qi1ugRPujlsHOdPXnCzQnhlytHYzRYCt'>
            <input type='hidden' id='typeDocument' name='typeDocument' value='CC'>
            <input type='text' id='username' name='username' value='1000000005'>
            <input type='password' id='password' name='password'
                   autocomplete='nop'
                   value='$2y$10$bsNWUpjwD/i04icfXZzkze4d5Maux6PgHqY2lrk5NCnYuaizTMKo6'>
            <input type='submit' value='Submit'>
        </form>
    </body>
"""


def _make_auth_manager():
    """Create an AuthManager with mock config for testing parsing."""
    config = MagicMock()
    return AuthManager(config)


class TestFieldPattern:
    """Test the FIELD_PATTERN regex directly."""

    def test_matches_single_quoted_attrs(self):
        html = "<input name='josso' value='abc123'>"
        matches = FIELD_PATTERN.findall(html)
        assert len(matches) == 1
        assert matches[0] == ("josso", "abc123")

    def test_matches_double_quoted_attrs(self):
        html = '<input name="josso" value="abc123">'
        matches = FIELD_PATTERN.findall(html)
        assert len(matches) == 1
        assert matches[0] == ("josso", "abc123")

    def test_matches_bcrypt_hash(self):
        html = "<input name='password' value='$2y$10$bsNWUpjwD/i04icfXZzkze4d5Maux6PgHqY2lrk5NCnYuaizTMKo6'>"
        matches = FIELD_PATTERN.findall(html)
        assert len(matches) == 1
        assert matches[0][0] == "password"
        assert matches[0][1].startswith("$2y$10$")


class TestMcfgPattern:
    """Test the MCFG_PATTERN regex."""

    def test_extracts_mcfg_json(self):
        html = 'M.cfg = {"sesskey":"qltpZtUW3K","contextInstanceId":718455};'
        match = MCFG_PATTERN.search(html)
        assert match is not None
        import json
        data = json.loads(match.group(1))
        assert data["sesskey"] == "qltpZtUW3K"
        assert data["contextInstanceId"] == 718455

    def test_multiline_mcfg(self):
        html = """M.cfg = {
            "sesskey": "abc123",
            "contextInstanceId": 12345
        };"""
        match = MCFG_PATTERN.search(html)
        assert match is not None


class TestParseWrapperResponse:
    """Test _parse_wrapper_response against known HTML structures."""

    def test_extracts_all_fields(self):
        mgr = _make_auth_manager()
        result = mgr._parse_wrapper_response(SAMPLE_WRAPPER_HTML)
        assert result["josso"] == "8teq07JHYfXpjPsF/HHtCQ=="
        assert result["logintoken"] == "Qi1ugRPujlsHOdPXnCzQnhlytHYzRYCt"
        assert result["typeDocument"] == "CC"
        assert result["username"] == "1000000005"
        assert result["password"].startswith("$2y$10$")

    def test_password_is_bcrypt_hash(self):
        mgr = _make_auth_manager()
        result = mgr._parse_wrapper_response(SAMPLE_WRAPPER_HTML)
        # bcrypt hashes start with $2y$ and are 60 chars
        assert result["password"].startswith("$2y$10$")
        assert len(result["password"]) == 60

    def test_raises_on_empty_html(self):
        mgr = _make_auth_manager()
        with pytest.raises(AuthError, match="no form fields found"):
            mgr._parse_wrapper_response("")

    def test_raises_on_html_without_form(self):
        mgr = _make_auth_manager()
        with pytest.raises(AuthError, match="no form fields found"):
            mgr._parse_wrapper_response("<html><body>Error</body></html>")

    def test_raises_on_missing_required_fields(self):
        mgr = _make_auth_manager()
        html = "<input name='logintoken' value='abc'><input name='password' value='x'>"
        with pytest.raises(AuthError, match="Missing required fields"):
            mgr._parse_wrapper_response(html)

    def test_raises_on_empty_josso(self):
        mgr = _make_auth_manager()
        html = (
            "<input name='josso' value=''>"
            "<input name='logintoken' value='abc'>"
            "<input name='typeDocument' value='CC'>"
            "<input name='username' value='123'>"
            "<input name='password' value='hash'>"
        )
        with pytest.raises(AuthError, match="Missing required fields"):
            mgr._parse_wrapper_response(html)
