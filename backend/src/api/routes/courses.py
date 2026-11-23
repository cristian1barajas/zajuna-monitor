"""Descubrimiento y selección de los cursos Zajuna que monitorea el instructor.

Flujo "Agregar grupo":
1. GET  /api/courses/discover — login con la cuenta Zajuna DEL instructor
   autenticado y lista de sus cursos (marcando los que ya sigue).
2. POST /api/courses/tracked  — guarda la selección; desde ahí el scraper
   la usa para saber qué cursos refrescar.
3. POST /api/scraper/run {fichas: [nueva]} — primera sincronización.
"""
from __future__ import annotations

import logging
from functools import partial

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_base_config
from src.api.executors import run_in_zajuna_pool
from src.auth.manager import AuthError, ZajunaUnavailableError
from src.config import ZajunaConfig
from src.models.programs import program_label
from src.scraper.course_discovery import discover_courses
from src.store import tracked_courses_store as tracked_store
from src.store import zajuna_accounts_store as vault

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/courses", tags=["courses"])


class CourseItem(BaseModel):
    course_id: int
    ficha: str
    shortname: str = ""
    fullname: str = ""
    program_code: str = ""
    program_label: str = ""
    tracked: bool = False


class DiscoverCoursesResponse(BaseModel):
    courses: list[CourseItem]
    truncated: bool


class TrackedCourseInput(BaseModel):
    course_id: int = Field(gt=0)
    ficha: str = Field(pattern=r"^\d{7}$")
    shortname: str = ""
    fullname: str = ""
    program_code: str = ""


class SaveTrackedRequest(BaseModel):
    courses: list[TrackedCourseInput]


class TrackedCoursesResponse(BaseModel):
    configured: bool  # False: el instructor aún no tiene registro (modo legado)
    courses: list[CourseItem]


def _item(course: dict, tracked: bool) -> CourseItem:
    return CourseItem(
        course_id=course["course_id"],
        ficha=course["ficha"],
        shortname=course.get("shortname", ""),
        fullname=course.get("fullname", ""),
        program_code=course.get("program_code", ""),
        program_label=program_label(
            course.get("program_code", ""), course.get("fullname", "")
        ),
        tracked=tracked,
    )


@router.get("/discover", response_model=DiscoverCoursesResponse)
async def discover(
    request: Request,
    config: ZajunaConfig = Depends(get_base_config),
) -> DiscoverCoursesResponse:
    """Lista los cursos de la cuenta Zajuna del instructor autenticado.

    Hace el login real contra Zajuna (10-30 s); corre en el pool dedicado.
    """
    user_id = request.state.user["id"]
    creds = vault.get_account_credentials(user_id)
    if creds is None:
        raise HTTPException(
            status_code=409,
            detail="Conecta tu cuenta Zajuna antes de buscar tus grupos.",
        )
    user_config = config.model_copy(
        update={
            "zajuna_type_document": creds["type_document"],
            "zajuna_document": creds["document"],
            "zajuna_password": creds["password"],
        }
    )

    try:
        result = await run_in_zajuna_pool(partial(discover_courses, user_config))
    except ZajunaUnavailableError as exc:
        logger.warning("Zajuna no disponible al descubrir cursos: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Zajuna no está respondiendo en este momento. Intenta de nuevo en unos minutos.",
        ) from exc
    except AuthError as exc:
        vault.mark_status(user_id, "invalid")
        logger.warning("Credenciales Zajuna rechazadas (usuario CMM %s): %s", user_id, exc)
        raise HTTPException(
            status_code=400,
            detail="Zajuna rechazó las credenciales guardadas. Actualízalas en Cuenta Zajuna.",
        ) from exc

    tracked_ids = set(tracked_store.tracked_course_ids(user_id) or [])
    courses = [
        _item(
            {
                "course_id": c.course_id,
                "ficha": c.ficha,
                "shortname": c.shortname,
                "fullname": c.fullname,
                "program_code": c.program_code,
            },
            tracked=c.course_id in tracked_ids,
        )
        for c in result.courses
    ]
    return DiscoverCoursesResponse(courses=courses, truncated=result.truncated)


@router.get("/tracked", response_model=TrackedCoursesResponse)
def get_tracked(request: Request) -> TrackedCoursesResponse:
    """Cursos que el instructor autenticado tiene seleccionados."""
    tracked = tracked_store.load_tracked(request.state.user["id"])
    if tracked is None:
        return TrackedCoursesResponse(configured=False, courses=[])
    return TrackedCoursesResponse(
        configured=True, courses=[_item(c, tracked=True) for c in tracked]
    )


@router.post("/tracked", response_model=TrackedCoursesResponse)
def save_tracked(body: SaveTrackedRequest, request: Request) -> TrackedCoursesResponse:
    """Reemplaza la selección de cursos del instructor autenticado."""
    fichas = [c.ficha for c in body.courses]
    duplicated = sorted({f for f in fichas if fichas.count(f) > 1})
    if duplicated:
        raise HTTPException(
            status_code=400,
            detail=f"Ficha repetida en la selección: {', '.join(duplicated)}",
        )
    saved = tracked_store.save_tracked(
        request.state.user["id"], [c.model_dump() for c in body.courses]
    )
    return TrackedCoursesResponse(
        configured=True, courses=[_item(c, tracked=True) for c in saved]
    )
