"""Juicios endpoints: RAP mapping, Sofia reports, and cross-reference."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_snapshot, verify_api_key
from src.api.juicios_por_asignar import compute_juicios_por_asignar
from src.api.rap_cross_engine import compute_rap_cross
from src.api.schemas import (
    JuiciosPorAsignarResponse,
    RapCrossResponse,
    RapMappingInput,
    RapMappingResponse,
    SofiaReportInput,
    SofiaReportResponse,
)
from src.store.novedades_store import load_novedades_set
from src.store.rap_mapping_store import (
    delete_rap_mapping,
    load_rap_mapping,
    save_rap_mapping,
)
from src.store.sofia_store import (
    delete_sofia_report,
    load_sofia_report,
    save_sofia_report,
)

router = APIRouter(prefix="/api/fichas/{ficha}", tags=["juicios"])


# --- RAP Mapping CRUD ---


@router.get("/rap-mapping", response_model=RapMappingResponse)
def get_rap_mapping(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Get the RAP mapping for a ficha."""
    data = load_rap_mapping(ficha)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No RAP mapping for ficha {ficha}")
    return RapMappingResponse(
        ficha=data["ficha"],
        program_name=data.get("program_name", ""),
        updated_at=data.get("updated_at", ""),
        mappings=data.get("mappings", []),
        stats=data.get("stats", {}),
    )


@router.post("/rap-mapping", response_model=RapMappingResponse)
def post_rap_mapping(
    ficha: str,
    body: RapMappingInput,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Save a RAP mapping for a ficha. Resolves item_ids from snapshot."""
    # Build evidence name→item_id lookup from snapshot. Keys are stored
    # space-stripped: gradebooks of older fichas contain typos like
    # "GA1- 220501092-AA3-EV03" that must still match the canonical code.
    evidence_lookup: dict[str, int] = {}
    for course in snapshot.get("courses", []):
        if course.get("ficha") != ficha:
            continue
        for ev in course.get("evidences", []):
            evidence_lookup[re.sub(r"\s+", "", ev["name"])] = ev["item_id"]

    # Resolve item_ids and build mappings
    mappings = []
    total_evidencias = 0
    matched_evidencias = 0

    for entry in body.mappings:
        evidencias = []
        for ev in entry.evidencias:
            item_id = ev.item_id
            matched = ev.matched

            # Try to resolve by code match if not already matched
            if item_id is None:
                code_key = re.sub(r"\s+", "", ev.code)
                for ev_name, ev_id in evidence_lookup.items():
                    if code_key in ev_name:
                        item_id = ev_id
                        matched = True
                        break

            total_evidencias += 1
            if matched or item_id is not None:
                matched_evidencias += 1

            evidencias.append({
                "code": ev.code,
                "item_id": item_id,
                "name": ev.name,
                "matched": matched or item_id is not None,
            })

        mappings.append({
            "fase": entry.fase,
            "competencia": entry.competencia,
            "rap": entry.rap,
            "rap_sofia_code": entry.rap_sofia_code,
            "evidencias": evidencias,
        })

    data = save_rap_mapping(ficha, {
        "program_name": body.program_name,
        "mappings": mappings,
        "stats": {
            "total_raps": len(mappings),
            "total_evidencias": total_evidencias,
            "matched_evidencias": matched_evidencias,
            "unmatched_evidencias": total_evidencias - matched_evidencias,
        },
    })

    return RapMappingResponse(
        ficha=data["ficha"],
        program_name=data["program_name"],
        updated_at=data["updated_at"],
        mappings=data["mappings"],
        stats=data["stats"],
    )


@router.delete("/rap-mapping")
def remove_rap_mapping(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Delete the RAP mapping for a ficha."""
    deleted = delete_rap_mapping(ficha)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No RAP mapping for ficha {ficha}")
    return {"deleted": True}


# --- Sofia Report CRUD ---


@router.get("/sofia-report", response_model=SofiaReportResponse)
def get_sofia_report(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Get the Sofia Plus report metadata for a ficha."""
    data = load_sofia_report(ficha)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No Sofia report for ficha {ficha}")
    return SofiaReportResponse(
        ficha=data["ficha"],
        program_name=data.get("program_name", ""),
        uploaded_at=data.get("uploaded_at", ""),
        total_students=data.get("total_students", 0),
        total_raps=data.get("total_raps", 0),
        students_count=len(data.get("students", [])),
        competency_map=data.get("competency_map", {}),
    )


@router.post("/sofia-report", response_model=SofiaReportResponse)
def post_sofia_report(
    ficha: str,
    body: SofiaReportInput,
    _key: str = Depends(verify_api_key),
):
    """Save a Sofia Plus report for a ficha."""
    students_data = [s.model_dump() for s in body.students]

    data = save_sofia_report(ficha, {
        "program_name": body.program_name,
        "total_students": body.total_students,
        "total_raps": body.total_raps,
        "students": students_data,
        "competency_map": body.competency_map,
    })

    return SofiaReportResponse(
        ficha=data["ficha"],
        program_name=data["program_name"],
        uploaded_at=data["uploaded_at"],
        total_students=data["total_students"],
        total_raps=data["total_raps"],
        students_count=len(data["students"]),
        competency_map=data["competency_map"],
    )


@router.delete("/sofia-report")
def remove_sofia_report(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Delete the Sofia Plus report for a ficha."""
    deleted = delete_sofia_report(ficha)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No Sofia report for ficha {ficha}")
    return {"deleted": True}


# --- Cross-Reference ---


@router.get("/rap-cross", response_model=RapCrossResponse)
def get_rap_cross(
    ficha: str,
    resultado: str | None = None,
    document: str | None = None,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Execute RAP cross-reference and return results."""
    rap_mapping = load_rap_mapping(ficha)
    if rap_mapping is None:
        raise HTTPException(status_code=404, detail=f"No RAP mapping for ficha {ficha}. Upload the evidence mapping first.")

    sofia_report = load_sofia_report(ficha)
    if sofia_report is None:
        raise HTTPException(status_code=404, detail=f"No Sofia report for ficha {ficha}. Upload the Sofia Plus report first.")

    result = compute_rap_cross(
        snapshot=snapshot,
        ficha=ficha,
        rap_mapping=rap_mapping,
        sofia_report=sofia_report,
        filter_resultado=resultado,
        filter_document=document,
    )

    return result


class JuiciosPorAsignarRequest(BaseModel):
    evidence_ids: list[int] = []


@router.post("/juicios-por-asignar", response_model=JuiciosPorAsignarResponse)
def post_juicios_por_asignar(
    ficha: str,
    body: JuiciosPorAsignarRequest,
    snapshot: dict = Depends(get_snapshot),
):
    """Aprendices a aprobar y a no aprobar en Sofía, por competencia y RAP, en orden alfabético.

    ``evidence_ids`` son las evidencias elegidas hasta el corte (como en Reportes). No
    salen quienes tienen novedad registrada ni los suspendidos en Zajuna.
    """
    rap_mapping = load_rap_mapping(ficha)
    if rap_mapping is None:
        raise HTTPException(status_code=404, detail=f"No RAP mapping for ficha {ficha}. Upload the evidence mapping first.")
    sofia_report = load_sofia_report(ficha)
    if sofia_report is None:
        raise HTTPException(status_code=404, detail=f"No Sofia report for ficha {ficha}. Upload the Sofia Plus report first.")
    if not any(c.get("ficha") == ficha for c in snapshot.get("courses", [])):
        raise HTTPException(status_code=404, detail=f"Ficha {ficha} not found")
    return compute_juicios_por_asignar(
        snapshot, ficha, rap_mapping, sofia_report, set(body.evidence_ids), load_novedades_set(ficha)
    )
