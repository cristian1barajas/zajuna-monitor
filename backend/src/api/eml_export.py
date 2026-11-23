"""Exporta borradores de correo del debido proceso como archivos .eml.

Cada .eml lleva la cabecera ``X-Unsent: 1``: en Outlook clásico, doble clic
lo abre como borrador listo para enviar; en el Outlook nuevo/web se abre
arrastrándolo al panel de lectura. Sin ``From``: Outlook pone la cuenta del
usuario. Solo stdlib (``email``, ``zipfile``).
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date
from email import policy
from email.message import EmailMessage

# Outlook y los clientes de Windows esperan CRLF.
_EML_POLICY = policy.default.clone(linesep="\r\n")

# Etiqueta corta de la etapa para el nombre del archivo.
STAGE_FILE_LABELS = {
    "primer_llamado": "Primer llamado",
    "segundo_llamado": "Segundo llamado",
    "plan_mejoramiento": "Plan de mejoramiento",
    "comite": "Comite de evaluacion",
}

_FORBIDDEN_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_SPACES = re.compile(r"\s+")
MAX_STEM_LENGTH = 80


@dataclass(frozen=True)
class EmlDraft:
    """Datos mínimos de un borrador para armar el .eml."""

    full_name: str
    subject: str
    body: str
    stage: str
    email: str = ""


def _single_line(value: str) -> str:
    """Colapsa saltos de línea: una cabecera no puede llevarlos."""
    return _SPACES.sub(" ", value).strip()


def build_eml(draft: EmlDraft) -> bytes:
    """Arma un .eml (RFC 5322) marcado como no enviado."""
    msg = EmailMessage(policy=_EML_POLICY)
    msg["X-Unsent"] = "1"
    to = _single_line(draft.email)
    if to:
        msg["To"] = to
    msg["Subject"] = _single_line(draft.subject)
    body = draft.body.replace("\r\n", "\n")
    if not body.endswith("\n"):
        body += "\n"
    msg.set_content(body, subtype="plain", charset="utf-8", cte="quoted-printable")
    return msg.as_bytes()


def safe_filename_part(value: str) -> str:
    """Texto apto para nombre de archivo en Windows (ASCII, sin \\/:*?"<>|)."""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = _FORBIDDEN_CHARS.sub(" ", folded)
    return _SPACES.sub(" ", cleaned).strip(" .")


def eml_filename(index: int, draft: EmlDraft) -> str:
    """``01 - Primer llamado - NOMBRE APELLIDO.eml``, recortado y seguro."""
    stage = STAGE_FILE_LABELS.get(draft.stage) or safe_filename_part(draft.stage) or "Llamado"
    name = safe_filename_part(draft.full_name) or "Aprendiz"
    stem = f"{index:02d} - {stage} - {name}"
    if len(stem) > MAX_STEM_LENGTH:
        stem = stem[:MAX_STEM_LENGTH].rstrip(" .-")
    return f"{stem}.eml"


def _unique(name: str, used: set[str]) -> str:
    """Evita colisiones (sin distinguir mayúsculas, como Windows)."""
    stem, ext = name.rsplit(".", 1)
    candidate = name
    n = 2
    while candidate.lower() in used:
        candidate = f"{stem} ({n}).{ext}"
        n += 1
    used.add(candidate.lower())
    return candidate


def zip_filename(ficha: str, today: date | None = None) -> str:
    """``correos-llamados-ficha-<ficha>-<AAAA-MM-DD>.zip``."""
    day = (today or date.today()).isoformat()
    return f"correos-llamados-ficha-{safe_filename_part(ficha) or 'sin-ficha'}-{day}.zip"


def build_eml_zip(drafts: list[EmlDraft]) -> tuple[bytes, list[str]]:
    """Empaqueta un .eml por borrador. Devuelve (bytes del zip, nombres)."""
    buffer = io.BytesIO()
    used: set[str] = set()
    names: list[str] = []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, draft in enumerate(drafts, 1):
            name = _unique(eml_filename(i, draft), used)
            zf.writestr(name, build_eml(draft))
            names.append(name)
    return buffer.getvalue(), names
