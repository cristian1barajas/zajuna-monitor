"""API endpoints for triggering the scraper."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api import dependencies
from src.api.dependencies import get_base_config
from src.api.schemas import ScraperRunRequest, ScraperStatusResponse, ScraperStepStatus
from src.config import ZajunaConfig
from src.scraper import job_manager
from src.store import tracked_courses_store as tracked_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["scraper"])


@router.post("/scraper/run", response_model=ScraperStatusResponse, status_code=202)
def trigger_scraper(
    body: ScraperRunRequest,
    request: Request,
    config: ZajunaConfig = Depends(get_base_config),
):
    """Launch a scraper run in the background (para el instructor autenticado)."""
    user = getattr(request.state, "user", None)
    cmm_user_id = user.get("id") if user else None

    if job_manager.is_running(cmm_user_id):
        raise HTTPException(
            status_code=409,
            detail="A scraper job is already running",
        )

    if body.fichas is None:
        # Todos los cursos del instructor: su registro. Los ZAJUNA_COURSE_IDS del
        # .env son de quien instaló el monitor; solo aplican sin instructor.
        course_ids = tracked_store.tracked_course_ids(cmm_user_id)
        if course_ids is None and cmm_user_id is None:
            course_ids = config.course_ids
    else:
        course_ids = _resolve_fichas_to_course_ids(body.fichas, request, cmm_user_id)

    if not course_ids:
        raise HTTPException(
            status_code=400,
            detail="No valid course IDs to scrape",
        )

    job = job_manager.start_job(config, course_ids, cmm_user_id=cmm_user_id)
    return _job_to_response(job)


@router.get("/scraper/status", response_model=ScraperStatusResponse)
def scraper_status(request: Request):
    """Estado del job de sincronización del instructor autenticado."""
    user = getattr(request.state, "user", None)
    job = job_manager.get_current_job(user.get("id") if user else None)
    if job is None:
        return ScraperStatusResponse(status="idle")
    return _job_to_response(job)


def _resolve_fichas_to_course_ids(
    fichas: list[str],
    request: Request | None,
    cmm_user_id: str | None,
) -> list[int]:
    """Ficha → course_id: primero el registro del instructor, luego su snapshot.

    El registro permite sincronizar una ficha recién agregada que aún no
    está en ningún snapshot. Una ficha que no aparece en ninguno se omite
    (sin caer a "todos los cursos": eso disparaba scrapes no pedidos).
    """
    ficha_map = tracked_store.course_ids_for_fichas(cmm_user_id, fichas)
    missing = {f for f in fichas if f not in ficha_map}
    if missing:
        try:
            snapshot = dependencies.load_snapshot(dependencies.snapshot_path_for(request))
        except HTTPException:  # 503: el instructor aún no tiene snapshot
            snapshot = {}
        for course in snapshot.get("courses", []):
            if course.get("ficha") in missing:
                ficha_map.setdefault(course["ficha"], course["course_id"])

    course_ids = []
    for ficha in fichas:
        if ficha in ficha_map:
            course_ids.append(ficha_map[ficha])
        else:
            logger.warning("Ficha %s no está en el registro ni en el snapshot", ficha)
    return course_ids


def _job_to_response(job) -> ScraperStatusResponse:
    """Convert ScraperJob to Pydantic response."""
    return ScraperStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        courses_total=job.courses_total,
        courses_done=job.courses_done,
        started_at=job.started_at,
        finished_at=job.finished_at,
        duration_seconds=job.duration_seconds,
        error=job.error,
        steps=[
            ScraperStepStatus(label=s.label, status=s.status)
            for s in job.steps
        ],
    )
