"""Import phone/contact data from SENA Excel (.xls) files into JSON store.

Excel structure (per file):
  Row 0: Title "Reporte de Aprendices"
  Row 1: "Ficha de Caracterización:" + ficha number
  Row 4: Headers (Tipo Doc, Número Doc, Nombre, Apellidos, Celular, Correo, Estado)
  Row 5+: Data rows

Filename pattern: "Reporte de Aprendices Ficha {FICHA}.xls"

Usage:
    python -m scripts.import_phone_data "C:\\Users\\crist\\Downloads\\Datos"
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import xlrd

# Add parent to path so we can import src modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.store.phone_data_store import save_phone_data

logger = logging.getLogger(__name__)

_FICHA_FROM_FILENAME = re.compile(r"Ficha\s+(\d+)")
_FICHA_FROM_CELL = re.compile(r"^(\d+)")

# Column indices (0-based)
COL_DOCUMENT = 1  # Número de Documento
COL_PHONE = 4     # Celular
DATA_START_ROW = 5  # First data row (after headers at row 4)


def extract_ficha_from_file(filepath: Path, sheet: xlrd.sheet.Sheet) -> str | None:
    """Extract ficha number from filename or cell B2."""
    # Try filename first
    m = _FICHA_FROM_FILENAME.search(filepath.stem)
    if m:
        return m.group(1)

    # Fallback: cell C2 contains "3388997 - ANALISIS Y DESARROLLO..."
    if sheet.nrows > 1:
        cell_val = str(sheet.cell_value(1, 2)).strip()
        m2 = _FICHA_FROM_CELL.match(cell_val)
        if m2:
            return m2.group(1)

    return None


def import_single_file(filepath: Path) -> tuple[str, dict[str, str]] | None:
    """Import phone data from a single .xls file.

    Returns (ficha, {document: phone}) or None if file cannot be parsed.
    """
    try:
        wb = xlrd.open_workbook(str(filepath))
    except Exception as e:
        logger.error("Cannot open %s: %s", filepath.name, e)
        return None

    sheet = wb.sheet_by_index(0)
    ficha = extract_ficha_from_file(filepath, sheet)
    if not ficha:
        logger.error("Cannot extract ficha from %s", filepath.name)
        return None

    phones: dict[str, str] = {}
    for row_idx in range(DATA_START_ROW, sheet.nrows):
        doc_val = sheet.cell_value(row_idx, COL_DOCUMENT)
        phone_val = sheet.cell_value(row_idx, COL_PHONE)

        # Document could be float (Excel stores numbers as float)
        document = str(int(doc_val)) if isinstance(doc_val, float) else str(doc_val).strip()
        phone = str(int(phone_val)) if isinstance(phone_val, float) else str(phone_val).strip()

        if document and phone:
            phones[document] = phone

    logger.info(
        "Parsed %s: ficha=%s, %d phones found",
        filepath.name, ficha, len(phones),
    )
    return ficha, phones


def import_folder(folder_path: str, allowed_fichas: set[str] | None = None) -> dict[str, int]:
    """Import all .xls files from a folder.

    Con ``allowed_fichas`` solo se guardan esas fichas (las del instructor).
    Returns {ficha: count} of imported entries.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    results: dict[str, int] = {}
    xls_files = sorted(folder.glob("*.xls"))

    if not xls_files:
        logger.warning("No .xls files found in %s", folder_path)
        return results

    for filepath in xls_files:
        result = import_single_file(filepath)
        if result:
            ficha, phones = result
            if allowed_fichas is not None and ficha not in allowed_fichas:
                logger.warning("Se omite %s: la ficha %s no es del instructor", filepath.name, ficha)
                continue
            save_phone_data(ficha, phones)
            results[ficha] = len(phones)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m scripts.import_phone_data <folder_path>")
        sys.exit(1)

    folder = sys.argv[1]
    results = import_folder(folder)

    print(f"\nImported phone data for {len(results)} fichas:")
    for ficha, count in sorted(results.items()):
        print(f"  Ficha {ficha}: {count} phones")
