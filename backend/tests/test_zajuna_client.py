"""ZajunaClient._request: reintentos ante 5xx, pausas y re-login fallido."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from src.client.zajuna import FetchError, ZajunaClient


def _response(status: int, text: str = "<html>ok</html>") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.url = "https://zajuna.sena.edu.co/zajuna/mod/forum/discuss.php?d=1"
    r.headers = {"content-type": "text/html"}
    if status >= 400:
        import requests

        r.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status}")
    return r


def _client(*responses) -> ZajunaClient:
    config = SimpleNamespace(
        zajuna_base_url="https://zajuna.sena.edu.co",
        request_timeout=60,
        min_delay=2.0,
        max_delay=5.0,
    )
    auth = MagicMock()
    auth.session.request.side_effect = list(responses)
    return ZajunaClient(auth, config)


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("src.client.zajuna.time.sleep") as sleep:
        yield sleep


def test_retries_a_5xx_and_returns_the_next_good_page():
    client = _client(_response(503), _response(200, "<html>bien</html>"))
    assert client.fetch_forum_discussion(1) == "<html>bien</html>"
    assert client.auth.session.request.call_count == 2


def test_three_5xx_in_a_row_raise_fetch_error():
    client = _client(_response(502), _response(503), _response(500))
    with pytest.raises(FetchError, match="tras 3 intentos"):
        client.fetch_forum_view(1)


def test_4xx_is_a_fetch_error_without_retrying():
    client = _client(_response(404))
    with pytest.raises(FetchError, match="404"):
        client.fetch_forum_view(1)
    assert client.auth.session.request.call_count == 1


def test_discussions_use_a_short_pause(_no_sleep):
    client = _client(_response(200), _response(200))
    client.fetch_forum_view(1)
    client.fetch_forum_discussion(2)
    (pause,), _ = _no_sleep.call_args
    assert 0.5 <= pause <= 1.5


def test_failed_relogin_is_a_fetch_error():
    expired = _response(200, '<input name="password">')
    client = _client(expired)
    client.auth.login.side_effect = RuntimeError("Zajuna caída")
    with pytest.raises(FetchError, match="no se pudo volver a entrar"):
        client.fetch_forum_view(1)
