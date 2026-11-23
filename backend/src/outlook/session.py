"""Inicio de sesión en Outlook Web y sesión en memoria por instructor.

El backend abre un Chrome visible con perfil temporal en Outlook Web; el
instructor inicia sesión con su correo SENA y, cuando la bandeja carga, se
toma el token que Outlook Web guardó en el navegador (o, si no está a la
vista, el que viaja en sus propias peticiones). El token sirve para buscar
los enviados por la API; Chrome se queda abierto y minimizado porque es el
que imprime cada correo con la opción "Imprimir" de Outlook.

Token y Chrome viven solo mientras dura la sesión: el token nunca va a disco
ni a logs, y al vencer (≈1 h) o al desconectar se cierra Chrome y se borra
su perfil.

Requiere que el backend corra en el equipo del instructor: Chrome se abre en
el escritorio de la máquina donde corre la API.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlparse

from src.outlook.chrome import CdpSession, ChromeError, ChromeProcess
from src.outlook.mail_client import API_BASES, MailApiError, OutlookMailClient, jwt_claims

logger = logging.getLogger(__name__)

OUTLOOK_URL = "https://outlook.office.com/mail/sentitems"
OWA_HOSTS = ("outlook.office.com", "outlook.office365.com", "outlook.cloud.microsoft", "outlook.live.com")
LOGIN_TIMEOUT_S = 300
# Tras cargar la bandeja, Outlook Web tarda unos segundos en pedir sus tokens.
EXTRACT_WINDOW_S = 60
# Margen para no usar un token a punto de vencer.
EXPIRY_MARGIN_S = 120

# Busca en sessionStorage/localStorage las entradas de MSAL con un JWT en "secret".
_STORAGE_TOKENS_JS = """
(() => {
  const out = [];
  for (const storage of [sessionStorage, localStorage]) {
    for (let i = 0; i < storage.length; i++) {
      const val = storage.getItem(storage.key(i));
      if (!val || !val.includes('eyJ')) continue;
      try {
        const parsed = JSON.parse(val);
        if (parsed && typeof parsed.secret === 'string' && parsed.secret.startsWith('eyJ')) out.push(parsed.secret);
      } catch (e) {}
    }
  }
  return out;
})()
"""


class LoginCancelled(RuntimeError):
    """El instructor cerró Chrome o se acabó el tiempo sin iniciar sesión."""


@dataclass
class OutlookCredentials:
    token: str
    base: str
    style: str
    account: str
    expires_at: datetime

    def client(self) -> OutlookMailClient:
        return OutlookMailClient(self.token, self.base, self.style)


@dataclass
class OutlookConnection:
    """Credenciales de la API y el Chrome con Outlook Web abierto (para imprimir)."""

    creds: OutlookCredentials
    chrome: ChromeProcess | None = None
    page: CdpSession | None = None
    # Una impresión a la vez: la pestaña de Outlook es una sola.
    lock: threading.Lock = field(default_factory=threading.Lock)

    def is_alive(self) -> bool:
        return self.chrome is None or self.chrome.is_running()

    def close(self) -> None:
        if self.page is not None:
            self.page.close()
        if self.chrome is not None:
            self.chrome.close()


def _is_mailbox(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in OWA_HOSTS and "/mail" in parsed.path


def _bearer_tokens_from_events(events: list[dict]) -> list[str]:
    tokens = []
    for ev in events:
        if ev.get("method") not in ("Network.requestWillBeSent", "Network.requestWillBeSentExtraInfo"):
            continue
        params = ev.get("params", {})
        headers = params.get("headers") or params.get("request", {}).get("headers") or {}
        for name, value in headers.items():
            if name.lower() == "authorization" and isinstance(value, str) and value.startswith("Bearer eyJ"):
                tokens.append(value[len("Bearer "):])
    return tokens


def credentials_from_tokens(
    tokens: list[str],
    client_factory: Callable[[str, str, str], OutlookMailClient] = OutlookMailClient,
) -> OutlookCredentials | None:
    """Primer token (no vencido) que la API de Outlook o Graph acepte."""
    now = time.time()
    seen = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        claims = jwt_claims(token)
        if claims.get("exp", 0) - EXPIRY_MARGIN_S <= now:
            continue
        aud = str(claims.get("aud", ""))
        for _name, base, style, audiences in API_BASES:
            if not any(a in aud for a in audiences):
                continue
            client = client_factory(token, base, style)
            try:
                client.probe()
            except MailApiError:
                continue
            account = claims.get("upn") or claims.get("unique_name") or claims.get("preferred_username") or ""
            return OutlookCredentials(
                token=token,
                base=base,
                style=style,
                account=str(account),
                expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
            )
    return None


def login_with_chrome(on_waiting: Callable[[str], None] = lambda _m: None) -> OutlookConnection:
    """Abre Chrome, espera a que el instructor entre a Outlook Web y deja la sesión lista.

    Si todo sale bien, Chrome queda abierto y minimizado; si no, se cierra.
    """
    chrome = ChromeProcess(headless=False, url=OUTLOOK_URL)
    chrome.start()
    page = None
    try:
        page = chrome.first_page()
        page.call("Network.enable")
        deadline = time.monotonic() + LOGIN_TIMEOUT_S
        in_mailbox_since: float | None = None
        seen_tokens: list[str] = []
        while time.monotonic() < deadline:
            if not chrome.is_running():
                raise LoginCancelled("Cerraste Chrome antes de terminar")
            try:
                href = page.evaluate("location.href", timeout=10) or ""
            except ChromeError:
                if not chrome.is_running():
                    raise LoginCancelled("Cerraste Chrome antes de terminar") from None
                time.sleep(1)
                continue

            seen_tokens.extend(_bearer_tokens_from_events(page.events))
            page.events.clear()

            if _is_mailbox(href):
                if in_mailbox_since is None:
                    in_mailbox_since = time.monotonic()
                    on_waiting("Outlook cargó; leyendo la sesión…")
                try:
                    stored = page.evaluate(_STORAGE_TOKENS_JS, timeout=10) or []
                except ChromeError:
                    stored = []
                creds = credentials_from_tokens(list(stored) + seen_tokens[::-1])
                if creds:
                    page.call("Network.disable")
                    page.events.clear()
                    chrome.minimize(page)
                    return OutlookConnection(creds=creds, chrome=chrome, page=page)
                if time.monotonic() - in_mailbox_since > EXTRACT_WINDOW_S:
                    raise ChromeError("Outlook cargó, pero no se encontró un token que sirva para leer los enviados")
            time.sleep(1.5)
        raise LoginCancelled("Se acabó el tiempo para iniciar sesión (5 min)")
    except BaseException:
        if page is not None:
            page.close()
        chrome.close()
        raise


EXPIRED_MESSAGE = "La sesión de Outlook venció; vuelve a conectar"
CLOSED_MESSAGE = "Se cerró la ventana de Chrome de Outlook; vuelve a conectar"


@dataclass
class _UserState:
    status: str = "idle"  # idle | waiting_login | connected | error
    message: str = ""
    conn: OutlookConnection | None = None


class OutlookSessionManager:
    """Una sesión de Outlook por usuario CMM, solo en memoria."""

    def __init__(self, login_fn: Callable[..., OutlookConnection] = login_with_chrome):
        self._login_fn = login_fn
        self._states: dict[str, _UserState] = {}
        self._lock = threading.Lock()

    def _drop(self, state: _UserState, status: str, message: str) -> None:
        conn, state.conn = state.conn, None
        state.status, state.message = status, message
        if conn is not None:
            # Cerrar Chrome tarda; que no bloquee el lock.
            threading.Thread(target=conn.close, daemon=True).start()

    def _state(self, user_id: str) -> _UserState:
        state = self._states.setdefault(user_id, _UserState())
        if state.conn is not None:
            if state.conn.creds.expires_at.timestamp() - EXPIRY_MARGIN_S <= time.time():
                self._drop(state, "idle", EXPIRED_MESSAGE)
            elif not state.conn.is_alive():
                self._drop(state, "idle", CLOSED_MESSAGE)
        return state

    @staticmethod
    def _public(state: _UserState) -> dict:
        creds = state.conn.creds if state.conn else None
        return {
            "status": state.status,
            "message": state.message,
            "account": creds.account if creds else None,
            "expires_at": creds.expires_at.isoformat() if creds else None,
        }

    def status(self, user_id: str) -> dict:
        with self._lock:
            return self._public(self._state(user_id))

    def start_login(self, user_id: str) -> dict:
        with self._lock:
            state = self._state(user_id)
            if state.status != "waiting_login":
                self._drop(state, "waiting_login", "Inicia sesión con tu correo SENA en la ventana de Chrome")
                threading.Thread(target=self._run_login, args=(user_id,), daemon=True).start()
            # Dentro del lock: el hilo de login no puede cambiarlo antes de responder.
            return self._public(state)

    def _set_message(self, user_id: str, message: str) -> None:
        with self._lock:
            self._states[user_id].message = message

    def _run_login(self, user_id: str) -> None:
        try:
            conn = self._login_fn(on_waiting=lambda m: self._set_message(user_id, m))
        except LoginCancelled as exc:
            self._finish(user_id, "idle", str(exc))
        except Exception as exc:  # noqa: BLE001 — se informa al instructor; nunca se registra el token
            logger.warning("Fallo el inicio de sesión en Outlook: %s", type(exc).__name__)
            self._finish(user_id, "error", str(exc) if isinstance(exc, ChromeError) else "No se pudo conectar con Outlook")
        else:
            self._finish(user_id, "connected", "", conn)

    def _finish(self, user_id: str, status: str, message: str, conn: OutlookConnection | None = None) -> None:
        with self._lock:
            state = self._states[user_id]
            state.status, state.message, state.conn = status, message, conn

    def disconnect(self, user_id: str) -> dict:
        with self._lock:
            state = self._state(user_id)
            if state.status != "waiting_login":
                self._drop(state, "idle", "")
            return self._public(state)

    def connection(self, user_id: str) -> OutlookConnection | None:
        with self._lock:
            return self._state(user_id).conn

    def expire(self, user_id: str) -> None:
        """La API rechazó el token antes de tiempo (p. ej. se revocó la sesión)."""
        with self._lock:
            self._drop(self._state(user_id), "idle", EXPIRED_MESSAGE)


session_manager = OutlookSessionManager()
