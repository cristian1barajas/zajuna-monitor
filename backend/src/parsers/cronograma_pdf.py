"""Parser del cronograma de actividades en PDF (uno por mes).

El PDF trae una sola tabla con columnas fijas:

    Semana | Ficha | Fase | Actividad de proyecto | Competencia | Resultado |
    Evidencia | Horas | Fecha inicial | Fecha final | Instructor

La celda de evidencia termina con el código, a veces partido en dos líneas
("... GA5-220501095-AA1-\\nEV04."). Las fechas vienen escritas
("Miércoles, 28 de octubre de 2026"); la de cierre es la fecha final, la
última de la fila.

No se depende de la posición de las columnas: cada fila se lee por su
contenido (códigos, fechas y número de ficha).
"""
from __future__ import annotations

import io
import re

CODE_RE = re.compile(r"GA\d+-\d{9}-AA\d+-EV\d+")
DATE_RE = re.compile(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.IGNORECASE)
FICHA_RE = re.compile(r"^\d{7}$")

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}


class CronogramaPdfError(Exception):
    """El archivo no es un PDF legible o no trae la tabla del cronograma."""


def parse_spanish_date(text: str) -> str | None:
    """'Miércoles, 28 de octubre de 2026' -> '2026-10-28'."""
    match = DATE_RE.search(text)
    if not match:
        return None
    day, month_name, year = match.groups()
    month = MONTHS.get(month_name.lower())
    if month is None:
        return None
    return f"{year}-{month:02d}-{int(day):02d}"


def _clean(cell: str | None) -> str:
    return re.sub(r"\s+", " ", cell or "").strip()


def entries_from_rows(rows: list[list[str | None]]) -> tuple[list[dict], list[str], set[str]]:
    """Convierte las filas de la tabla en entradas del cronograma.

    Devuelve (entradas, avisos, fichas encontradas). Una evidencia repetida
    queda con su fecha de cierre más reciente.
    """
    cutoffs: dict[str, str] = {}
    warnings: list[str] = []
    fichas: set[str] = set()

    for row in rows:
        cells = [_clean(c) for c in row]
        fichas.update(c for c in cells if FICHA_RE.match(c))

        # Los códigos pueden venir partidos por saltos de línea o espacios
        codes: list[str] = []
        for cell in row:
            for code in CODE_RE.findall(re.sub(r"\s", "", cell or "")):
                if code not in codes:
                    codes.append(code)

        dates = [d for d in (parse_spanish_date(c) for c in cells) if d]
        evidence_text = next((c for c in cells if c.lower().startswith("evidencia")), "")

        if not codes:
            if evidence_text:
                warnings.append(f"Fila sin código de evidencia: «{evidence_text[:90]}»")
            continue
        if not dates:
            warnings.append(f"{', '.join(codes)} no trae fecha final")
            continue

        cutoff = dates[-1]
        for code in codes:
            if code not in cutoffs or cutoff > cutoffs[code]:
                cutoffs[code] = cutoff

    entries = [
        {"evidence_name": code, "cutoff_date": date}
        for code, date in sorted(cutoffs.items(), key=lambda item: (item[1], item[0]))
    ]
    return entries, warnings, fichas


def extract_rows(content: bytes) -> list[list[str | None]]:
    """Filas de todas las tablas del PDF."""
    if not content.startswith(b"%PDF"):
        raise CronogramaPdfError("no es un PDF")

    import pdfplumber  # import tardío: solo lo usa la carga del cronograma

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return [
                row
                for page in pdf.pages
                for table in page.extract_tables()
                for row in table
            ]
    except Exception as exc:  # pdfminer lanza varios tipos según el daño del archivo
        raise CronogramaPdfError("no se pudo leer el PDF") from exc


def parse_cronograma_pdf(content: bytes) -> tuple[list[dict], list[str], set[str]]:
    """Lee un PDF de cronograma: (entradas, avisos, fichas encontradas)."""
    rows = extract_rows(content)
    if not rows:
        raise CronogramaPdfError("no se encontró la tabla del cronograma")
    return entries_from_rows(rows)
