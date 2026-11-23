"""Reconoce los correos de debido proceso por su asunto y arma el ZIP de soportes.

Los asuntos salen de ``src/api/email_templates.py``, p. ej.
``Primer llamado de atención - Ficha 3389000 - NOMBRE APELLIDO``; también se
aceptan los que el instructor escribió a mano con la misma idea.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date

# (etapa, carpeta en el ZIP, patrón sobre el asunto sin tildes y en minúsculas)
STAGES = [
    ("primer_llamado", "1. Primer llamado", re.compile(r"\bprimer\s+llamado")),
    ("segundo_llamado", "2. Segundo llamado", re.compile(r"\bsegundo\s+llamado")),
    ("tercer_llamado", "3. Tercer llamado", re.compile(r"\btercer\s+llamado")),
    ("plan_mejoramiento", "4. Plan de mejoramiento", re.compile(r"\bplan\s+de\s+mejoramiento")),
    ("comite", "5. Comite de evaluacion", re.compile(r"\bcomite\b")),
]
STAGE_FOLDERS = {key: folder for key, folder, _ in STAGES}
# Prefijo del ZIP cuando todos los correos son de una sola etapa.
STAGE_ZIP_PREFIX = {
    "primer_llamado": "Primer_llamado",
    "segundo_llamado": "Segundo_llamado",
    "tercer_llamado": "Tercer_llamado",
    "plan_mejoramiento": "Plan_mejoramiento",
    "comite": "Comite",
}

_REPLY_PREFIX = re.compile(r"^\s*(re|rv|fw|fwd|reenviar|responder)\s*:", re.IGNORECASE)
_FICHA = re.compile(r"\b(?:ficha|grupo)\s*(?:n[o°º.]*\s*)?[:\-]?\s*(\d{6,8})\b", re.IGNORECASE)
_NAME_AFTER_FICHA = re.compile(r"\b(?:ficha|grupo)\s*[:\-]?\s*\d{6,8}\s*[-–—:]\s*(.+)$", re.IGNORECASE)
_FORBIDDEN_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def fold(text: str) -> str:
    """Minúsculas y sin tildes, para comparar asuntos."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


@dataclass(frozen=True)
class LlamadoInfo:
    stage: str
    ficha: str | None
    student_name: str


def classify_subject(subject: str) -> LlamadoInfo | None:
    """Etapa, grupo y aprendiz del asunto; ``None`` si no es un correo de debido proceso.

    Las respuestas y reenvíos (RE:, RV:, FW:) no cuentan: el soporte es el envío original.
    """
    if _REPLY_PREFIX.match(subject):
        return None
    folded = fold(subject)
    stage = next((key for key, _folder, pattern in STAGES if pattern.search(folded)), None)
    if stage is None:
        return None
    ficha_match = _FICHA.search(subject)
    name_match = _NAME_AFTER_FICHA.search(subject.strip())
    return LlamadoInfo(
        stage=stage,
        ficha=ficha_match.group(1) if ficha_match else None,
        student_name=name_match.group(1).strip() if name_match else "",
    )


def safe_filename(value: str, max_length: int = 90) -> str:
    cleaned = _FORBIDDEN_CHARS.sub("-", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(". ")
    return cleaned[:max_length] or "correo"


@dataclass(frozen=True)
class PdfEntry:
    stage: str
    student_name: str
    subject: str
    sent_date: str  # YYYY-MM-DD en hora de Colombia
    pdf: bytes


def build_zip(entries: list[PdfEntry]) -> tuple[bytes, list[str]]:
    """Un PDF por correo, en una carpeta por etapa: ``1. Primer llamado/NOMBRE - 2026-10-02.pdf``.

    Devuelve el ZIP y la ruta de cada PDF dentro de él, en el orden de ``entries``.
    """
    buf = io.BytesIO()
    used: set[str] = set()
    paths: list[str] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for e in entries:
            stem = safe_filename(f"{e.student_name or e.subject} - {e.sent_date}")
            path = f"{STAGE_FOLDERS.get(e.stage, 'Otros')}/{stem}.pdf"
            n = 2
            while path.lower() in used:
                path = f"{STAGE_FOLDERS.get(e.stage, 'Otros')}/{stem} ({n}).pdf"
                n += 1
            used.add(path.lower())
            paths.append(path)
            zf.writestr(path, e.pdf)
    return buf.getvalue(), paths


def zip_filename(ficha: str, stages: set[str], day: date) -> str:
    """Nombre corto del ZIP de un día, para reconocerlo al subirlo a Zajuna.

    La fecha va como en las actas (``DD-MM-AA``): ``Llamados_3389000_02-10-26.zip``
    (varias etapas) o ``Comite_3389000_29-10-26.zip`` (una sola etapa).
    """
    prefix = STAGE_ZIP_PREFIX.get(next(iter(stages)), "Llamados") if len(stages) == 1 else "Llamados"
    return f"{prefix}_{ficha}_{day:%d-%m-%y}.zip"
