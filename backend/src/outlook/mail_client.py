"""Cliente de los Elementos enviados de Outlook con el token de Outlook Web.

Graph y la API REST directa están bloqueadas en el tenant SENA para apps de
terceros (requieren consentimiento de un administrador), pero el token que
Outlook Web obtiene para sí mismo sí sirve. Se prueban las bases conocidas y
se queda la primera que responde; las respuestas se normalizan porque la API
de Outlook usa PascalCase y Graph camelCase.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from urllib.parse import quote

import requests

# Colombia no tiene horario de verano: UTC-5 todo el año.
COLOMBIA_TZ = timezone(timedelta(hours=-5), name="COT")

# (nombre, base, estilo de nombres de campo, audiencias del token que acepta)
API_BASES = [
    ("outlook", "https://outlook.office.com/api/v2.0", "pascal", ("outlook.office.com", "outlook.office365.com")),
    ("outlook365", "https://outlook.office365.com/api/v2.0", "pascal", ("outlook.office.com", "outlook.office365.com")),
    ("graph", "https://graph.microsoft.com/v1.0", "camel", ("graph.microsoft.com", "00000003-0000-0000-c000-000000000000")),
]

_TIMEOUT = 30
_PAGE_SIZE = 100
_MAX_PAGES = 20


class MailApiError(RuntimeError):
    """La API de Outlook rechazó la consulta (token vencido, permisos, red)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def jwt_claims(token: str) -> dict:
    """Claims del JWT sin verificar firma (solo para leer aud, exp y la cuenta)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return {}


@dataclass
class SentMessage:
    id: str
    subject: str
    sent_at: datetime  # en hora de Colombia
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)


def _field(item: dict, name: str, default=None):
    """Lee un campo en PascalCase (Outlook) o camelCase (Graph)."""
    if name in item:
        return item[name]
    camel = name[0].lower() + name[1:]
    return item.get(camel, default)


def _addresses(recipients: list[dict] | None) -> list[str]:
    out = []
    for r in recipients or []:
        addr = _field(r, "EmailAddress", {}) or {}
        value = _field(addr, "Address", "") or ""
        if value:
            out.append(value)
    return out


def _parse_sent_at(value: str) -> datetime:
    # La API devuelve UTC con "Z" y a veces 7 decimales.
    value = re.sub(r"(\.\d{6})\d+", r"\1", value.replace("Z", "+00:00"))
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(COLOMBIA_TZ)


def _to_message(item: dict) -> SentMessage:
    return SentMessage(
        id=_field(item, "Id", ""),
        subject=_field(item, "Subject", "") or "",
        sent_at=_parse_sent_at(_field(item, "SentDateTime", "")),
        to=_addresses(_field(item, "ToRecipients")),
        cc=_addresses(_field(item, "CcRecipients")),
    )


def _day_bounds_utc(day: date) -> tuple[str, str]:
    """Inicio y fin del día en Colombia, expresados en UTC para el $filter."""
    start = datetime(day.year, day.month, day.day, tzinfo=COLOMBIA_TZ)
    end = start + timedelta(days=1)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.astimezone(UTC).strftime(fmt), end.astimezone(UTC).strftime(fmt)


class OutlookMailClient:
    def __init__(self, token: str, base: str, style: str, session: requests.Session | None = None):
        self.base = base
        self.style = style
        self._http = session or requests.Session()
        self._http.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

    def _f(self, name: str) -> str:
        return name if self.style == "pascal" else name[0].lower() + name[1:]

    def _get(self, url: str, params: dict | None = None) -> dict:
        try:
            resp = self._http.get(url, params=params, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            raise MailApiError("No se pudo conectar con Outlook") from exc
        if resp.status_code == 401:
            raise MailApiError("La sesión de Outlook venció", status=401)
        if resp.status_code >= 400:
            raise MailApiError(f"Outlook respondió {resp.status_code}", status=resp.status_code)
        return resp.json()

    def probe(self) -> None:
        """Lanza ``MailApiError`` si esta base no acepta el token."""
        self._get(f"{self.base}/me/mailFolders/SentItems/messages", {"$top": "1", "$select": self._f("Subject")})

    def list_sent_on(self, day: date) -> list[SentMessage]:
        """Correos enviados ese día (hora de Colombia), sin cuerpo."""
        start, end = _day_bounds_utc(day)
        sent = self._f("SentDateTime")
        params: dict | None = {
            "$filter": f"{sent} ge {start} and {sent} lt {end}",
            "$select": ",".join(self._f(n) for n in ("Subject", "SentDateTime", "ToRecipients", "CcRecipients")),
            "$orderby": f"{sent} asc",
            "$top": str(_PAGE_SIZE),
        }
        url: str | None = f"{self.base}/me/mailFolders/SentItems/messages"
        out: list[SentMessage] = []
        for _ in range(_MAX_PAGES):
            if not url:
                break
            data = self._get(url, params)
            out.extend(_to_message(item) for item in data.get("value", []))
            url = data.get("@odata.nextLink")
            params = None  # el nextLink ya trae los parámetros
        return out

    def get_message(self, message_id: str) -> SentMessage:
        """Datos del correo, sin cuerpo: el PDF lo imprime Outlook Web."""
        fields = ("Id", "Subject", "SentDateTime", "ToRecipients", "CcRecipients")
        item = self._get(
            f"{self.base}/me/messages/{quote(message_id, safe='')}",
            {"$select": ",".join(self._f(n) for n in fields)},
        )
        return _to_message(item)
