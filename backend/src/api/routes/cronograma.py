"""Cronograma endpoints: manage evidence cutoff dates per ficha."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.api.dependencies import get_snapshot, verify_api_key
from src.api.schemas import (
    CronogramaEntryResponse,
    CronogramaInput,
    CronogramaPdfFile,
    CronogramaPdfPreview,
    CronogramaResponse,
)
from src.parsers.cronograma_pdf import CronogramaPdfError, parse_cronograma_pdf
from src.store.cronograma_store import (
    delete_cronograma,
    load_cronograma,
    resolve_evidence_id,
    save_cronograma,
)

router = APIRouter(prefix="/api", tags=["cronograma"])


def _build_response(data: dict, snapshot: dict) -> CronogramaResponse:
    """Build CronogramaResponse, resolving evidence_item_ids from snapshot."""
    ficha = data["ficha"]
    entries = []
    for entry in data.get("entries", []):
        item_id = entry.get("evidence_item_id")
        if item_id is None:
            item_id = resolve_evidence_id(entry["evidence_name"], snapshot, ficha)
        entries.append(CronogramaEntryResponse(
            evidence_name=entry["evidence_name"],
            evidence_item_id=item_id,
            cutoff_date=entry["cutoff_date"],
        ))
    return CronogramaResponse(
        ficha=ficha,
        entries=entries,
        updated_at=data.get("updated_at", ""),
    )


@router.get("/cronograma/{ficha}", response_model=CronogramaResponse)
def get_cronograma(
    ficha: str,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Get the cronograma for a ficha."""
    data = load_cronograma(ficha)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No cronograma for ficha {ficha}")
    return _build_response(data, snapshot)


@router.post("/cronograma/{ficha}", response_model=CronogramaResponse)
def post_cronograma(
    ficha: str,
    body: CronogramaInput,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Create or replace the cronograma for a ficha."""
    entries = []
    for entry in body.entries:
        item_id = resolve_evidence_id(entry.evidence_name, snapshot, ficha)
        entries.append({
            "evidence_name": entry.evidence_name,
            "evidence_item_id": item_id,
            "cutoff_date": entry.cutoff_date,
        })

    data = save_cronograma(ficha, entries)
    return _build_response(data, snapshot)


MAX_PDF_FILES = 24
MAX_PDF_BYTES = 10 * 1024 * 1024


@router.post("/cronograma/{ficha}/pdf", response_model=CronogramaPdfPreview)
def preview_cronograma_pdf(
    ficha: str,
    files: list[UploadFile] = File(...),
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Lee los PDF del cronograma (uno por mes) sin guardar nada.

    Devuelve las evidencias con su fecha de cierre para que el instructor las
    revise; se guardan después con POST /cronograma/{ficha}. Si una evidencia
    sale en varios meses, queda la fecha más reciente.
    """
    if len(files) > MAX_PDF_FILES:
        raise HTTPException(status_code=413, detail=f"Máximo {MAX_PDF_FILES} archivos a la vez")

    cutoffs: dict[str, str] = {}
    warnings: list[str] = []
    summary: list[CronogramaPdfFile] = []

    for upload in files:
        name = upload.filename or "archivo"
        content = upload.file.read(MAX_PDF_BYTES + 1)
        if len(content) > MAX_PDF_BYTES:
            warnings.append(f"{name}: pesa más de 10 MB, no se leyó")
            summary.append(CronogramaPdfFile(filename=name, entries=0))
            continue
        try:
            entries, file_warnings, fichas = parse_cronograma_pdf(content)
        except CronogramaPdfError as exc:
            warnings.append(f"{name}: {exc}")
            summary.append(CronogramaPdfFile(filename=name, entries=0))
            continue

        if fichas and ficha not in fichas:
            warnings.append(
                f"{name}: es de la ficha {', '.join(sorted(fichas))}, no de la {ficha}; no se tomó"
            )
            summary.append(CronogramaPdfFile(filename=name, entries=0))
            continue

        warnings.extend(f"{name}: {w}" for w in file_warnings)
        summary.append(CronogramaPdfFile(filename=name, entries=len(entries)))
        for entry in entries:
            code, date = entry["evidence_name"], entry["cutoff_date"]
            if code not in cutoffs or date > cutoffs[code]:
                cutoffs[code] = date

    if not cutoffs:
        raise HTTPException(
            status_code=422,
            detail="No se encontraron evidencias con fecha en los PDF. " + " · ".join(warnings),
        )

    return CronogramaPdfPreview(
        entries=[
            CronogramaEntryResponse(
                evidence_name=code,
                evidence_item_id=resolve_evidence_id(code, snapshot, ficha),
                cutoff_date=date,
            )
            for code, date in sorted(cutoffs.items(), key=lambda item: (item[1], item[0]))
        ],
        warnings=warnings,
        files=summary,
    )


@router.delete("/cronograma/{ficha}")
def remove_cronograma(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Delete the cronograma for a ficha."""
    deleted = delete_cronograma(ficha)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No cronograma for ficha {ficha}")
    return {"deleted": True}
