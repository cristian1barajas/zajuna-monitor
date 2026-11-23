"""Mueve los datos por ficha de la carpeta común a la de un instructor.

Antes del multi-instructor los stores guardaban ``data/<store>/<ficha>.json``;
ahora guardan ``data/<store>/<id del instructor>/<ficha>.json``. Este script
pasa los archivos existentes al instructor que los creó (en una instalación
de un solo instructor, su id del CMM).

Uso (desde backend/):
    python -m scripts.migrar_datos_por_instructor 2            # solo muestra
    python -m scripts.migrar_datos_por_instructor 2 --aplicar  # mueve
    python -m scripts.migrar_datos_por_instructor 2 --revertir --aplicar

No pisa nada: si el destino ya existe, ese archivo se deja y se avisa.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from src.config import (
    ACTAS_DIR,
    ASSIGNMENTS_DIR,
    CRONOGRAMAS_DIR,
    DATA_DIR,
    DUE_PROCESS_DIR,
    NOVEDADES_DIR,
    RAP_MAPPINGS_DIR,
    SOFIA_REPORTS_DIR,
    SOPORTES_DIR,
    SUBMISSION_STATUS_DIR,
)
from src.store.instructor_scope import validate_user_id

STORE_DIRS = [
    ASSIGNMENTS_DIR,
    CRONOGRAMAS_DIR,
    DUE_PROCESS_DIR,
    NOVEDADES_DIR,
    DATA_DIR / "phone_data",
    RAP_MAPPINGS_DIR,
    SOFIA_REPORTS_DIR,
    SOPORTES_DIR,
    ACTAS_DIR,
    SUBMISSION_STATUS_DIR,
]

FICHA_FILE = re.compile(r"^\d{1,15}\.json$")


def plan(user_id: str, revertir: bool = False) -> list[tuple[Path, Path]]:
    """Pares (origen, destino) de los archivos de ficha a mover."""
    moves: list[tuple[Path, Path]] = []
    for base in STORE_DIRS:
        source_dir, target_dir = (base / user_id, base) if revertir else (base, base / user_id)
        if not source_dir.is_dir():
            continue
        for path in sorted(source_dir.iterdir()):
            if path.is_file() and FICHA_FILE.match(path.name):
                moves.append((path, target_dir / path.name))
    return moves


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("instructor", help="id del instructor en el CMM (p. ej. 2)")
    parser.add_argument("--aplicar", action="store_true", help="mover de verdad (sin esto solo se muestra)")
    parser.add_argument("--revertir", action="store_true", help="devolver los archivos a la carpeta común")
    args = parser.parse_args(argv)

    user_id = validate_user_id(args.instructor)
    moves = plan(user_id, args.revertir)
    if not moves:
        print("No hay archivos por mover.")
        return 0

    omitidos = 0
    for source, target in moves:
        rel = f"{source.relative_to(DATA_DIR)} -> {target.relative_to(DATA_DIR)}"
        if target.exists():
            omitidos += 1
            print(f"  OMITIDO (ya existe el destino): {rel}")
            continue
        print(f"  {'movido' if args.aplicar else 'se movería'}: {rel}")
        if args.aplicar:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)

    total = len(moves) - omitidos
    if args.aplicar:
        print(f"Listo: {total} archivos movidos, {omitidos} omitidos.")
    else:
        print(f"{total} archivos por mover, {omitidos} omitidos. Agrega --aplicar para hacerlo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
