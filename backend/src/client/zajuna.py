"""Authenticated HTTP client for Zajuna."""
from __future__ import annotations

import logging
import random
import time

import requests

from src.auth.manager import AuthManager
from src.config import ZajunaConfig

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Raised when a fetch operation fails."""


class ZajunaClient:
    """Authenticated HTTP client for Zajuna.

    Responsibilities:
    - Human-like delays between requests (2-5s random)
    - Logging of every request (URL, status, timing)
    - Detection of session expiry with auto re-login
    - Request counting for monitoring
    """

    def __init__(self, auth: AuthManager, config: ZajunaConfig) -> None:
        self.auth = auth
        self.config = config
        self._request_count: int = 0

    def fetch_grader(self, course_id: int) -> str:
        """Fetch the grader report HTML for a given course.

        GET /zajuna/grade/report/grader/index.php?id={course_id}

        Returns the raw HTML string.
        Raises FetchError if the response does not contain the grader table.
        """
        path = f"/zajuna/grade/report/grader/index.php?id={course_id}"
        html = self._request("GET", path)

        if 'id="user-grades"' not in html:
            raise FetchError(
                f"Grader report not found in response for course {course_id}. "
                f"Response length: {len(html)} chars. "
                "The course may not exist or the user may not have permission."
            )

        logger.info(
            "Fetched grader for course %d (%d chars)", course_id, len(html)
        )
        return html

    def fetch_participants(self, course_id: int) -> str:
        """Fetch the participants page HTML for a given course.

        GET /zajuna/user/index.php?id={course_id}&perpage=5000

        Returns the raw HTML string.
        Raises FetchError if the response does not contain the participants table.
        """
        path = f"/zajuna/user/index.php?id={course_id}&perpage=5000"
        html = self._request("GET", path)

        if 'id="participants"' not in html:
            raise FetchError(
                f"Participants table not found in response for course {course_id}. "
                f"Response length: {len(html)} chars. "
                "The course may not exist or the user may not have permission."
            )

        logger.info(
            "Fetched participants for course %d (%d chars)", course_id, len(html)
        )
        return html

    def fetch_assignments_index(self, course_id: int) -> str:
        """Fetch the assignments index page HTML for a given course.

        GET /zajuna/mod/assign/index.php?id={course_id}

        Returns the raw HTML string.
        Raises FetchError if the response does not contain assignment links.
        """
        path = f"/zajuna/mod/assign/index.php?id={course_id}"
        html = self._request("GET", path)

        if "/mod/assign/view.php" not in html:
            raise FetchError(
                f"No assignment links found in response for course {course_id}. "
                f"Response length: {len(html)} chars. "
                "The course may have no assignments."
            )

        logger.info(
            "Fetched assignments index for course %d (%d chars)",
            course_id, len(html),
        )
        return html

    def fetch_assignment_detail(self, cmid: int) -> str:
        """Fetch an individual assignment page HTML.

        GET /zajuna/mod/assign/view.php?id={cmid}

        Returns the raw HTML string.
        """
        path = f"/zajuna/mod/assign/view.php?id={cmid}"
        html = self._request("GET", path)

        logger.info(
            "Fetched assignment detail for cmid %d (%d chars)", cmid, len(html)
        )
        return html

    def fetch_submissions_list(self, cmid: int) -> str:
        """Fetch the grading/submissions list HTML for an assignment.

        GET /zajuna/mod/assign/view.php?id={cmid}&action=grading&tifirst=&tilast=&perpage=-1

        Forces "Todos" on both name filters and disables pagination
        to ensure ALL students are returned regardless of user's
        previously saved filter state in the Moodle session.

        Returns the raw HTML string with the submissions table.
        """
        path = (
            f"/zajuna/mod/assign/view.php?id={cmid}"
            f"&action=grading&tifirst=&tilast=&perpage=-1"
        )
        html = self._request("GET", path)

        logger.info(
            "Fetched submissions list for cmid %d (%d chars)", cmid, len(html)
        )
        return html

    def download_file(self, url: str) -> tuple[bytes, str]:
        """Download a binary file from Zajuna.

        Args:
            url: Full or relative URL to download. Typically a pluginfile.php
                 or /Repositorio/ URL.

        Returns:
            (content_bytes, filename) tuple.
        """
        content, headers = self._request_binary(url)

        # Extract filename from Content-Disposition header
        filename = ""
        cd = headers.get("content-disposition", "")
        if "filename=" in cd:
            # Handle both filename="name" and filename*=UTF-8''name
            for part in cd.split(";"):
                part = part.strip()
                if part.startswith("filename="):
                    filename = part.split("=", 1)[1].strip('"').strip("'")
                elif part.startswith("filename*="):
                    # RFC 5987: filename*=UTF-8''encoded_name
                    encoded = part.split("''", 1)[-1] if "''" in part else ""
                    if encoded:
                        from urllib.parse import unquote
                        filename = unquote(encoded)

        # Fallback: extract from URL path
        if not filename:
            from urllib.parse import unquote, urlparse
            path = urlparse(url).path
            filename = unquote(path.rsplit("/", 1)[-1]) if "/" in path else "download"

        logger.info("Downloaded file: %s (%d bytes)", filename, len(content))
        return content, filename

    def _request_binary(
        self,
        url: str,
        max_retries: int = 1,
    ) -> tuple[bytes, dict]:
        """Execute an HTTP GET and return binary content + headers.

        Args:
            url: Full or relative URL.
            max_retries: Retry attempts on session expiry.

        Returns:
            (content_bytes, response_headers) tuple.
        """
        if not self.auth.session:
            raise FetchError("No authenticated session. Call auth.login() first.")

        if self._request_count > 0:
            self._human_delay()

        # Handle relative URLs
        if url.startswith("/"):
            url = f"{self.config.zajuna_base_url}{url}"

        start = time.monotonic()
        logger.debug("[%d] GET (binary) %s", self._request_count + 1, url)

        response = self.auth.session.get(
            url,
            timeout=self.config.request_timeout,
            stream=True,
        )
        elapsed = time.monotonic() - start
        self._request_count += 1

        logger.debug(
            "[%d] GET (binary) -> %d (%.2fs, %d bytes)",
            self._request_count, response.status_code, elapsed,
            len(response.content),
        )

        if self._is_session_expired(response):
            if max_retries > 0:
                logger.warning("Session expired during download, re-authenticating...")
                self.auth.login()
                return self._request_binary(url, max_retries=max_retries - 1)
            else:
                raise FetchError("Session expired and max retries reached")

        response.raise_for_status()
        return response.content, dict(response.headers)

    def fetch_quiz_index(self, course_id: int) -> str:
        """Fetch the quiz index page HTML for a given course.

        GET /zajuna/mod/quiz/index.php?id={course_id}

        Returns the raw HTML string.
        Raises FetchError if no quiz links are found.
        """
        path = f"/zajuna/mod/quiz/index.php?id={course_id}"
        html = self._request("GET", path)

        if "view.php?id=" not in html or "generaltable" not in html:
            raise FetchError(
                f"No quiz table found in response for course {course_id}. "
                f"Response length: {len(html)} chars. "
                "The course may have no quizzes."
            )

        logger.info(
            "Fetched quiz index for course %d (%d chars)",
            course_id, len(html),
        )
        return html

    def fetch_forum_index(self, course_id: int) -> str:
        """Fetch the forum index page HTML for a given course.

        GET /zajuna/mod/forum/index.php?id={course_id}

        Returns the raw HTML string.
        Raises FetchError if no forum links are found.
        """
        path = f"/zajuna/mod/forum/index.php?id={course_id}"
        html = self._request("GET", path)

        if "view.php?f=" not in html:
            raise FetchError(
                f"No forum links found in response for course {course_id}. "
                f"Response length: {len(html)} chars. "
                "The course may have no forums."
            )

        logger.info(
            "Fetched forum index for course %d (%d chars)",
            course_id, len(html),
        )
        return html

    def fetch_forum_view(self, forum_id: int) -> str:
        """Fetch a forum view page HTML (discussion listing).

        GET /zajuna/mod/forum/view.php?f={forum_id}

        Returns the raw HTML string.
        """
        path = f"/zajuna/mod/forum/view.php?f={forum_id}"
        html = self._request("GET", path)

        logger.info(
            "Fetched forum view for forum_id %d (%d chars)", forum_id, len(html)
        )
        return html

    def fetch_forum_discussion(self, discussion_id: int) -> str:
        """Fetch a forum discussion page HTML (individual posts).

        GET /zajuna/mod/forum/discuss.php?d={discussion_id}

        Returns the raw HTML string.
        """
        path = f"/zajuna/mod/forum/discuss.php?d={discussion_id}"
        # Pausa corta: es pasar de un hilo al siguiente dentro del mismo foro.
        # Con la pausa normal (2-5 s) un foro de 16 hilos tardaba ~1 min más.
        html = self._request("GET", path, delay_range=(0.5, 1.5))

        logger.info(
            "Fetched forum discussion %d (%d chars)", discussion_id, len(html)
        )
        return html

    def _request(
        self,
        method: str,
        path: str,
        max_retries: int = 1,
        delay_range: tuple[float, float] | None = None,
        **kwargs,
    ) -> str:
        """Execute an HTTP request with delay, logging, and session recovery.

        Args:
            method: HTTP method (GET, POST)
            path: URL path relative to base_url
            max_retries: Number of retry attempts on session expiry
            delay_range: (min, max) seconds of human delay; defaults to config
            **kwargs: Additional arguments passed to session.request()

        Returns:
            Response body as text.
        """
        if not self.auth.session:
            raise FetchError("No authenticated session. Call auth.login() first.")

        # Human delay before request (skip on first request of session)
        if self._request_count > 0:
            self._human_delay(delay_range)

        url = f"{self.config.zajuna_base_url}{path}"
        start = time.monotonic()

        logger.debug("[%d] %s %s", self._request_count + 1, method, url)

        # Errores transitorios de Zajuna (corta respuestas a mitad de stream,
        # timeouts, resets, 5xx): reintentar con espera creciente antes de rendirse.
        transient_errors = (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        )
        last_exc: Exception | None = None
        response = None
        for attempt in range(3):
            if attempt > 0:
                wait = 5 * (2 ** (attempt - 1))  # 5s, 10s
                logger.warning(
                    "Error transitorio de Zajuna en %s %s (intento %d/3): %s — "
                    "reintentando en %ds",
                    method, path, attempt, last_exc, wait,
                )
                time.sleep(wait)
            try:
                response = self.auth.session.request(
                    method,
                    url,
                    timeout=self.config.request_timeout,
                    **kwargs,
                )
            except transient_errors as exc:
                last_exc = exc
                continue
            if response.status_code < 500:
                break
            last_exc = requests.exceptions.HTTPError(f"{response.status_code} Server Error")
            response = None
        if response is None:
            raise FetchError(
                f"Zajuna cortó la conexión en {method} {path} tras 3 intentos: {last_exc}"
            ) from last_exc

        elapsed = time.monotonic() - start
        self._request_count += 1

        logger.debug(
            "[%d] %s %s -> %d (%.2fs)",
            self._request_count, method, path,
            response.status_code, elapsed,
        )

        # Check for session expiry
        if self._is_session_expired(response):
            if max_retries > 0:
                logger.warning("Session expired, re-authenticating...")
                try:
                    self.auth.login()
                except Exception as exc:
                    raise FetchError(f"La sesión de Zajuna venció y no se pudo volver a entrar: {exc}") from exc
                return self._request(
                    method, path, max_retries=max_retries - 1,
                    delay_range=delay_range, **kwargs
                )
            else:
                raise FetchError("Session expired and max retries reached")

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise FetchError(f"Zajuna respondió {response.status_code} en {method} {path}") from exc
        return response.text

    def _human_delay(self, delay_range: tuple[float, float] | None = None) -> None:
        """Sleep for a random duration between min_delay and max_delay."""
        low, high = delay_range or (self.config.min_delay, self.config.max_delay)
        delay = random.uniform(low, high)
        logger.debug("Sleeping %.1fs...", delay)
        time.sleep(delay)

    def _is_session_expired(self, response: requests.Response) -> bool:
        """Detect if the response indicates an expired session.

        Indicators:
        - Redirect to login page (URL contains /login/index.php without testsession)
        - Response HTML contains a password input field (Moodle login form)
        """
        # Check URL after redirects
        final_url = response.url
        if "/login/index.php" in final_url and "testsession" not in final_url:
            return True

        # Check for login form in response body
        if response.headers.get("content-type", "").startswith("text/html"):
            text = response.text
            if 'name="password"' in text and 'id="loginForm"' not in text:
                return True

        return False

    @property
    def request_count(self) -> int:
        return self._request_count
