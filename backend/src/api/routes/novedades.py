"""API endpoints for student novedades (administrative novelties)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_snapshot, verify_api_key
from src.store.novedades_store import (
    NOVEDAD_TYPES,
    delete_all_novedades,
    load_novedades,
    remove_novedades,
    save_novedades,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["novedades"])


class NovedadRequest(BaseModel):
    user_ids: list[int]
    type: str = "cancelacion"
    note: str = ""


class NovedadRecord(BaseModel):
    user_id: int
    full_name: str
    document: str
    type: str
    type_label: str
    note: str
    created_at: str
    updated_at: str


class NovedadesResponse(BaseModel):
    ficha: str
    total: int
    types: dict[str, str]
    records: list[NovedadRecord]


class RemoveNovedadRequest(BaseModel):
    user_ids: list[int]


@router.get("/fichas/{ficha}/novedades", response_model=NovedadesResponse)
def get_novedades(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Get all novedades for a ficha."""
    data = load_novedades(ficha)
    records = []
    if data:
        for rec in data.get("records", {}).values():
            records.append(NovedadRecord(**rec))

    return NovedadesResponse(
        ficha=ficha,
        total=len(records),
        types=NOVEDAD_TYPES,
        records=records,
    )


@router.post("/fichas/{ficha}/novedades", response_model=NovedadesResponse)
def add_novedades(
    ficha: str,
    body: NovedadRequest,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Add novedades for students in a ficha."""
    if not body.user_ids:
        raise HTTPException(status_code=400, detail="user_ids cannot be empty")

    if body.type not in NOVEDAD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type: {body.type}. Valid: {list(NOVEDAD_TYPES.keys())}",
        )

    data = save_novedades(
        ficha=ficha,
        user_ids=body.user_ids,
        type_=body.type,
        note=body.note,
        snapshot=snapshot,
    )

    records = [NovedadRecord(**r) for r in data.get("records", {}).values()]
    return NovedadesResponse(
        ficha=ficha,
        total=len(records),
        types=NOVEDAD_TYPES,
        records=records,
    )


@router.post("/fichas/{ficha}/novedades/remove", response_model=NovedadesResponse)
def remove_novedades_endpoint(
    ficha: str,
    body: RemoveNovedadRequest,
    _key: str = Depends(verify_api_key),
):
    """Remove novedades for specific students."""
    if not body.user_ids:
        raise HTTPException(status_code=400, detail="user_ids cannot be empty")

    data = remove_novedades(ficha, body.user_ids)
    records = [NovedadRecord(**r) for r in data.get("records", {}).values()]
    return NovedadesResponse(
        ficha=ficha,
        total=len(records),
        types=NOVEDAD_TYPES,
        records=records,
    )


@router.delete("/fichas/{ficha}/novedades")
def delete_novedades(
    ficha: str,
    _key: str = Depends(verify_api_key),
):
    """Delete all novedades for a ficha."""
    deleted = delete_all_novedades(ficha)
    if not deleted:
        raise HTTPException(status_code=404, detail="No novedades found")
    return {"deleted": True}
