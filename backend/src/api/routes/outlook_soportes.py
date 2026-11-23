"""Soportes de los llamados de atención: correos enviados en Outlook → PDF → ZIP por etapa.

Flujo: conectar Outlook (Chrome temporal, ver ``src/outlook/session.py``) →
buscar los correos de un grupo en las fechas de envío elegidas → imprimir los
seleccionados con la opción "Imprimir" de Outlook (trabajo en segundo plano) →
descargar un ZIP por día de envío, con una carpeta por etapa.
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.api.dependencies import get_snapshot
from src.outlook.export_jobs import ExportBusy, export_jobs
from src.outlook.llamados import STAGES, classify_subject
from src.outlook.mail_client import MailApiError, OutlookMailClient
from src.outlook.session import EXPIRED_MESSAGE, OutlookConnection, session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["outlook-soportes"])

STAGE_KEYS = [key for key, _folder, _pattern in STAGES]
MAX_FECHAS = 31
MAX_CORREOS_ZIP = 300


class OutlookSessionStatus(BaseModel):
    status: str
    message: str
    account: str | None
    expires_at: str | None


class BuscarLlamadosRequest(BaseModel):
    fechas: list[date] = Field(min_length=1, max_length=MAX_FECHAS)
    etapas: list[str] = Field(default_factory=lambda: list(STAGE_KEYS))


class CorreoLlamado(BaseModel):
    id: str
    subject: str
    sent_at: str
    sent_date: str
    stage: str
    student_name: str
    to: list[str]


class BuscarLlamadosResponse(BaseModel):
    ficha: str
    correos: list[CorreoLlamado]
    revisados: int


class ZipLlamadosRequest(BaseModel):
    message_ids: list[str] = Field(min_length=1, max_length=MAX_CORREOS_ZIP)


class ZipJobStatus(BaseModel):
    job_id: str
    status: str
    done: int
    total: int
    message: str
    # Un ZIP por día de envío; se descargan por su posición en esta lista.
    archivos: list[str]


def _user_id(request: Request) -> str:
    return str(request.state.user["id"])


def _require_ficha(snapshot: dict, ficha: str) -> None:
    if not any(c.get("ficha") == ficha for c in snapshot.get("courses", [])):
        raise HTTPException(status_code=404, detail=f"Ficha {ficha} not found")


def _require_conn(user_id: str) -> OutlookConnection:
    conn = session_manager.connection(user_id)
    if conn is None:
        raise HTTPException(status_code=409, detail="Conecta Outlook antes de buscar los correos")
    return conn


def _mail_error(user_id: str, exc: MailApiError) -> HTTPException:
    if exc.status == 401:
        session_manager.expire(user_id)
        return HTTPException(status_code=409, detail=EXPIRED_MESSAGE)
    return HTTPException(status_code=502, detail=str(exc))


def _client(conn: OutlookConnection) -> OutlookMailClient:
    return conn.creds.client()


@router.get("/outlook/session", response_model=OutlookSessionStatus)
def get_outlook_session(request: Request):
    return session_manager.status(_user_id(request))


@router.post("/outlook/session", response_model=OutlookSessionStatus)
def start_outlook_session(request: Request):
    """Abre Chrome en el equipo donde corre la API para que el instructor inicie sesión."""
    return session_manager.start_login(_user_id(request))


@router.delete("/outlook/session", response_model=OutlookSessionStatus)
def disconnect_outlook_session(request: Request):
    return session_manager.disconnect(_user_id(request))


@router.post("/fichas/{ficha}/soportes-llamados/buscar", response_model=BuscarLlamadosResponse)
def buscar_llamados(
    ficha: str,
    body: BuscarLlamadosRequest,
    request: Request,
    snapshot: dict = Depends(get_snapshot),
):
    """Correos de debido proceso del grupo enviados en esas fechas (sin cuerpo)."""
    _require_ficha(snapshot, ficha)
    unknown = sorted(set(body.etapas) - set(STAGE_KEYS))
    if unknown:
        raise HTTPException(status_code=422, detail=f"Etapas desconocidas: {', '.join(unknown)}")
    user_id = _user_id(request)
    client = _client(_require_conn(user_id))

    correos: list[CorreoLlamado] = []
    revisados = 0
    try:
        for day in sorted(set(body.fechas)):
            for msg in client.list_sent_on(day):
                revisados += 1
                info = classify_subject(msg.subject)
                if info is None or info.ficha != ficha or info.stage not in body.etapas:
                    continue
                correos.append(
                    CorreoLlamado(
                        id=msg.id,
                        subject=msg.subject,
                        sent_at=msg.sent_at.isoformat(),
                        sent_date=msg.sent_at.date().isoformat(),
                        stage=info.stage,
                        student_name=info.student_name,
                        to=msg.to,
                    )
                )
    except MailApiError as exc:
        raise _mail_error(user_id, exc) from exc

    correos.sort(key=lambda c: (STAGE_KEYS.index(c.stage), c.student_name, c.sent_at))
    return BuscarLlamadosResponse(ficha=ficha, correos=correos, revisados=revisados)


@router.post("/fichas/{ficha}/soportes-llamados/zip", response_model=ZipJobStatus)
def start_zip_llamados(
    ficha: str,
    body: ZipLlamadosRequest,
    request: Request,
    snapshot: dict = Depends(get_snapshot),
):
    """Empieza a imprimir los correos con Outlook; el avance se consulta con el id del trabajo.

    Cada correo se vuelve a leer de Outlook y se exige que su asunto sea de
    debido proceso de este grupo: el ZIP no puede llevar otros correos.
    """
    _require_ficha(snapshot, ficha)
    user_id = _user_id(request)
    conn = _require_conn(user_id)
    try:
        job = export_jobs.start(user_id, ficha, conn, body.message_ids, on_expired=lambda: session_manager.expire(user_id))
    except ExportBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return job.public()


def _job_or_404(request: Request, ficha: str, job_id: str):
    job = export_jobs.get(_user_id(request), job_id)
    if job is None or job.ficha != ficha:
        raise HTTPException(status_code=404, detail="La descarga ya no está disponible")
    return job


@router.get("/fichas/{ficha}/soportes-llamados/zip/{job_id}", response_model=ZipJobStatus)
def zip_llamados_status(ficha: str, job_id: str, request: Request):
    return _job_or_404(request, ficha, job_id).public()


@router.get("/fichas/{ficha}/soportes-llamados/zip/{job_id}/archivo/{indice}")
def zip_llamados_file(ficha: str, job_id: str, indice: int, request: Request):
    """ZIP de un día: un PDF por correo (impreso por Outlook), en carpetas por etapa."""
    job = _job_or_404(request, ficha, job_id)
    if job.status != "done":
        raise HTTPException(status_code=409, detail="La descarga todavía no está lista")
    if not 0 <= indice < len(job.files):
        raise HTTPException(status_code=404, detail="Ese archivo no existe en la descarga")
    filename, data = job.files[indice]
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
