"""Actas del equipo ejecutor (Word) con la relación de llamados enviados cada día.

La relación sale de Debido proceso (quién, documento y etapa registrados ese
día) y del registro de soportes de Outlook (hora real del correo y ZIP). El
acta se llena por código sobre la plantilla del formato SENA.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from src.api.dependencies import get_snapshot
from src.outlook.acta import (
    STAGE_ORDER,
    ActaInput,
    Asistente,
    acta_filename,
    build_acta,
    collect_llamados,
)
from src.outlook.llamados import fold
from src.store.due_process_store import load_due_process
from src.store.soportes_store import load_acta_config, load_soportes, save_acta_config

router = APIRouter(prefix="/api", tags=["actas-equipo-ejecutor"])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class AsistenteModel(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    dependencia: str = Field(default="SENA/CMM", max_length=80)


class FechaActa(BaseModel):
    fecha_envio: str
    llamados: int
    por_etapa: dict[str, int]
    soportes: int
    acta_numero: int | None


class SoporteRegistro(BaseModel):
    message_id: str
    stage: str
    student_name: str
    sent_at: str
    to: list[str]
    archivo: str
    zip: str
    descargado_at: str


class ActasResponse(BaseModel):
    ficha: str
    asistentes: list[AsistenteModel]
    siguiente_numero: int
    hora_inicio: str
    hora_fin: str
    fechas: list[FechaActa]
    soportes: list[SoporteRegistro]


class ActaRequest(BaseModel):
    fecha_envio: date
    numero: int = Field(ge=1, le=9999)
    fecha_acta: date | None = None
    hora_inicio: str = Field(min_length=1, max_length=20)
    hora_fin: str = Field(min_length=1, max_length=20)
    asistentes: list[AsistenteModel] = Field(min_length=1, max_length=12)


def _course(snapshot: dict, ficha: str) -> dict:
    for c in snapshot.get("courses", []):
        if c.get("ficha") == ficha:
            return c
    raise HTTPException(status_code=404, detail=f"Ficha {ficha} not found")


def _due_records(ficha: str) -> list[dict]:
    return list((load_due_process(ficha) or {}).get("records", {}).values())


@router.get("/fichas/{ficha}/actas-equipo-ejecutor", response_model=ActasResponse)
def get_actas(ficha: str, snapshot: dict = Depends(get_snapshot)):
    """Fechas con llamados (y cuántos tienen soporte de Outlook), más lo último usado en las actas."""
    _course(snapshot, ficha)
    config = load_acta_config(ficha)
    soportes = load_soportes(ficha)
    generadas = {g["fecha_envio"]: g["numero"] for g in config.get("generadas", [])}

    days: dict[str, Counter] = {}
    for rec in _due_records(ficha):
        for h in rec.get("history", []):
            days.setdefault(h["date"][:10], Counter())[h["stage"]] += 1
    soportes_por_dia = Counter(s["sent_at"][:10] for s in soportes)
    for day in soportes_por_dia:
        days.setdefault(day, Counter())

    fechas = [
        FechaActa(
            fecha_envio=day,
            llamados=sum(counts.values()),
            por_etapa={s: counts[s] for s in STAGE_ORDER if counts[s]},
            soportes=soportes_por_dia.get(day, 0),
            acta_numero=generadas.get(day),
        )
        for day, counts in sorted(days.items(), reverse=True)
    ]
    return ActasResponse(
        ficha=ficha,
        asistentes=config["asistentes"],
        siguiente_numero=int(config["ultimo_numero"] or 0) + 1,
        hora_inicio=config["hora_inicio"],
        hora_fin=config["hora_fin"],
        fechas=fechas,
        soportes=sorted(soportes, key=lambda s: (s["sent_at"], s["student_name"])),
    )


@router.post("/fichas/{ficha}/actas-equipo-ejecutor")
def generate_acta(ficha: str, body: ActaRequest, snapshot: dict = Depends(get_snapshot)):
    """Acta en Word con la relación de llamados enviados en ``fecha_envio`` y firmas en blanco."""
    course = _course(snapshot, ficha)
    documentos = {
        " ".join(fold(s.get("full_name", "")).split()): s.get("document", "")
        for s in course.get("students", [])
    }
    soportes = load_soportes(ficha)
    llamados, del_dia = collect_llamados(_due_records(ficha), soportes, body.fecha_envio, documentos)
    if not llamados:
        raise HTTPException(status_code=404, detail=f"No hay llamados registrados el {body.fecha_envio.isoformat()}")

    zips = sorted({s["zip"] for s in del_dia if s.get("zip")})
    data = ActaInput(
        numero=str(body.numero),
        ficha=ficha,
        fecha_envio=body.fecha_envio,
        fecha_acta=body.fecha_acta or body.fecha_envio,
        hora_inicio=body.hora_inicio.strip(),
        hora_fin=body.hora_fin.strip(),
        asistentes=[Asistente(a.nombre.strip(), a.dependencia.strip()) for a in body.asistentes],
        llamados=llamados,
        anexo_zip=", ".join(zips),
        soportes=len(del_dia),
    )
    content = build_acta(data)
    save_acta_config(
        ficha,
        numero=body.numero,
        asistentes=[a.model_dump() for a in body.asistentes],
        hora_inicio=data.hora_inicio,
        hora_fin=data.hora_fin,
        fecha_envio=body.fecha_envio.isoformat(),
    )
    return Response(
        content=content,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{acta_filename(data.fecha_acta)}"'},
    )
