"""Authentication manager for Zajuna (SENA Moodle wrapper)."""
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable

import requests
import urllib3

from src.config import ZajunaConfig

# Suppress InsecureRequestWarning due to verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Realistic browser User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Regex for hidden form fields (single or double quoted HTML attributes)
FIELD_PATTERN = re.compile(
    r"name=['\"](\w+)['\"][^>]*value=['\"](.*?)['\"]",
    re.IGNORECASE,
)

# Regex for M.cfg JSON block
MCFG_PATTERN = re.compile(r"M\.cfg\s*=\s*(\{.*?\});", re.DOTALL)


class AuthError(Exception):
    """Login falló por credenciales rechazadas o respuesta inesperada."""


class ZajunaUnavailableError(Exception):
    """Zajuna no respondió (5xx / cortes de red) tras reintentar.

    Es un problema de infraestructura, NO de credenciales: quien lo capture
    no debe marcar la cuenta como inválida ni pedir al usuario re-ingresar
    su contraseña.
    """


class AuthManager:
    """Manages the full authentication flow against Zajuna.

    Flow:
    1. POST /controllers/login_user/singIn.php -> extract hidden form
    2. POST /zajuna/login/index.php -> follow 303 redirect
    3. GET /zajuna/my/ -> validate session is active
    """

    def __init__(self, config: ZajunaConfig) -> None:
        self.config = config
        self.session: requests.Session | None = None
        self._authenticated: bool = False
        self._user_id: int | None = None
        self._sesskey: str | None = None
        # HTML de /zajuna/my/ (paso 3): trae el bloque "Mis cursos" que usa
        # el descubrimiento de cursos, sin pedir la página de nuevo.
        self._my_page_html: str | None = None

    def _request_with_retry(
        self, do_request: Callable[[], requests.Response]
    ) -> requests.Response:
        """Ejecuta una petición HTTP reintentando errores transitorios de Zajuna.

        Zajuna corta respuestas a mitad de stream y responde 5xx de forma
        intermitente. Estos son errores de infraestructura, no de credenciales:
        se reintentan hasta 3 veces con espera creciente (5s, 10s). Un 4xx
        (credenciales rechazadas) NO se reintenta — falla de inmediato.
        """
        transient_errors = (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        )
        last_exc: Exception | None = None
        for attempt in range(3):
            if attempt > 0:
                wait = 5 * (2 ** (attempt - 1))  # 5s, 10s
                logger.warning(
                    "Error transitorio de Zajuna en login (intento %d/3): %s — "
                    "reintentando en %ds",
                    attempt, last_exc, wait,
                )
                time.sleep(wait)
            try:
                response = do_request()
                # 5xx = Zajuna caída/inestable → transitorio; reintentar
                if response.status_code >= 500:
                    last_exc = requests.exceptions.HTTPError(
                        f"{response.status_code} Server Error"
                    )
                    continue
                return response
            except transient_errors as exc:
                last_exc = exc
        raise ZajunaUnavailableError(
            f"Zajuna no respondió tras 3 intentos durante el login: {last_exc}"
        ) from last_exc

    def login(self) -> requests.Session:
        """Execute the full login flow. Returns the authenticated session."""
        logger.info(
            "Starting login flow for document %s...",
            self.config.zajuna_document[:4] + "****",
        )

        self.session = self._create_session()

        # Step 1: Wrapper login
        form_data = self._step1_wrapper_login()

        # Step 2: Moodle login
        self._step2_moodle_login(form_data)

        # Step 3: Validate session
        self._step3_validate_session()

        self._authenticated = True
        logger.info(
            "Login successful. User ID: %s, sesskey: %s",
            self._user_id,
            self._sesskey[:4] + "****" if self._sesskey else None,
        )
        return self.session

    def _create_session(self) -> requests.Session:
        """Create a requests.Session with realistic headers."""
        session = requests.Session()
        session.verify = False
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })
        return session

    def _step1_wrapper_login(self) -> dict:
        """POST to the SENA wrapper singIn.php, parse the hidden form.

        Returns dict with keys: josso, logintoken, typeDocument, username, password
        The 'password' value is a bcrypt hash generated server-side.
        """
        url = f"{self.config.zajuna_base_url}/controllers/login_user/singIn.php"
        payload = {
            "typeDocument": self.config.zajuna_type_document,
            "document": self.config.zajuna_document,
            "password": self.config.zajuna_password,
            "form_login_user": "",
        }

        logger.debug("Step 1: POST %s", url)
        response = self._request_with_retry(
            lambda: self.session.post(
                url,
                data=payload,
                timeout=self.config.request_timeout,
            )
        )
        response.raise_for_status()

        form_data = self._parse_wrapper_response(response.text)
        logger.debug(
            "Step 1 complete. Extracted fields: %s",
            list(form_data.keys()),
        )
        return form_data

    def _parse_wrapper_response(self, html: str) -> dict:
        """Extract hidden form fields from the wrapper response HTML.

        Expected HTML structure (single-quoted attributes):
            <form id='loginForm' action='/zajuna/login/index.php' ...>
                <input type='hidden' name='josso' value='TOKEN'>
                <input type='hidden' name='logintoken' value='TOKEN'>
                <input type='hidden' name='typeDocument' value='CC'>
                <input type='text' name='username' value='1000000005'>
                <input type='password' name='password' value='$2y$10$...'>
            </form>
        """
        matches = FIELD_PATTERN.findall(html)
        if not matches:
            raise AuthError(
                "Failed to parse wrapper response: no form fields found. "
                f"Response length: {len(html)} chars"
            )

        form_data = dict(matches)

        # Validate required fields
        required = ["josso", "logintoken", "typeDocument", "username", "password"]
        missing = [f for f in required if f not in form_data or not form_data[f]]
        if missing:
            raise AuthError(f"Missing required fields from wrapper: {missing}")

        return form_data

    def _step2_moodle_login(self, form_data: dict) -> None:
        """POST to /zajuna/login/index.php with wrapper data.

        Follows the 303 redirect automatically.
        Verifies MoodleSessionsenazajunav cookie is set.
        """
        url = f"{self.config.zajuna_base_url}/zajuna/login/index.php"
        payload = {
            "josso": form_data["josso"],
            "logintoken": form_data["logintoken"],
            "typeDocument": form_data["typeDocument"],
            "username": form_data["username"],
            "password": form_data["password"],
        }

        logger.debug("Step 2: POST %s", url)
        self._request_with_retry(
            lambda: self.session.post(
                url,
                data=payload,
                allow_redirects=True,
                timeout=self.config.request_timeout,
            )
        )

        # Check for Moodle session cookie
        cookie_names = [c.name for c in self.session.cookies]
        if "MoodleSessionsenazajunav" not in cookie_names:
            raise AuthError(
                "MoodleSessionsenazajunav cookie not set after login. "
                f"Cookies received: {cookie_names}"
            )

        logger.debug("Step 2 complete. Moodle session cookie acquired.")

    def _step3_validate_session(self) -> None:
        """GET /zajuna/my/ and validate the session is active.

        Checks:
        - M.cfg.contextInstanceId != 0
        - sesskey is present
        - HTML contains dashboard indicators
        - HTML does NOT contain password input (login form)
        """
        url = f"{self.config.zajuna_base_url}/zajuna/my/"
        logger.debug("Step 3: GET %s", url)
        response = self._request_with_retry(
            lambda: self.session.get(url, timeout=self.config.request_timeout)
        )
        response.raise_for_status()
        html = response.text

        # Check no login form present
        if 'name="password"' in html or "name='password'" in html:
            raise AuthError(
                "Session validation failed: login form detected in /my/ response"
            )

        # Check for dashboard indicators
        if not any(marker in html for marker in [
            "Área Personal", "Área personal", "Mis cursos", "Hola"
        ]):
            raise AuthError(
                "Session validation failed: no dashboard content detected"
            )

        # Extract M.cfg
        mcfg_match = MCFG_PATTERN.search(html)
        if not mcfg_match:
            raise AuthError("Session validation failed: M.cfg not found in HTML")

        try:
            mcfg = json.loads(mcfg_match.group(1))
        except json.JSONDecodeError as e:
            raise AuthError(f"Failed to parse M.cfg JSON: {e}") from e

        # Extract sesskey
        self._sesskey = mcfg.get("sesskey")
        if not self._sesskey:
            raise AuthError(
                "Session validation failed: sesskey not found in M.cfg"
            )

        # Extract user ID
        context_id = mcfg.get("contextInstanceId", 0)
        if context_id == 0:
            raise AuthError(
                "Session validation failed: contextInstanceId is 0 "
                "(indicates not authenticated)"
            )
        self._user_id = context_id
        self._my_page_html = html

        logger.debug("Step 3 complete. User ID: %s", self._user_id)

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    @property
    def user_id(self) -> int | None:
        return self._user_id

    @property
    def sesskey(self) -> str | None:
        return self._sesskey

    @property
    def my_page_html(self) -> str | None:
        return self._my_page_html
