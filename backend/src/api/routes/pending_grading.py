"""API endpoints for pending grading (assignment + forum submission checking)."""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_config, get_snapshot
from src.api.executors import run_in_zajuna_pool
from src.api.schemas import (
    AssignmentMappingItem,
    AssignmentMappingResponse,
    GradingWaitingStudent,
    PendingGradingRequest,
    PendingGradingResponse,
    PendingGradingResult,
)
from src.auth.manager import AuthManager
from src.client.zajuna import FetchError, ZajunaClient
from src.config import ZajunaConfig
from src.parsers.assignment_detail import parse_assignment_detail
from src.parsers.forum_detail import parse_forum_discussions, parse_forum_posts_grading
from src.parsers.grader import ParseError
from src.parsers.submissions_list import parse_submissions_page
from src.store.assignments_store import load_assignments

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fichas", tags=["pending-grading"])

# Sesión de Zajuna compartida entre consultas de "Por calificar". El frontend
# pide una evidencia por petición; con un login por petición eran ~90 logins
# seguidos y Zajuna empezaba a rechazarlos a mitad de la consulta (503).
# El cliente vuelve a entrar solo si la sesión vence.
_SESSION_IDLE_TTL = 20 * 60  # segundos sin uso antes de descartar la sesión
_sessions: dict[int, tuple[ZajunaClient, float]] = {}
_account_locks: dict[int, threading.Lock] = {}
_registry_lock = threading.Lock()


def _account_key(config: ZajunaConfig) -> int:
    return hash((config.zajuna_document, config.zajuna_password))


def _account_lock(config: ZajunaConfig) -> threading.Lock:
    """Una consulta a la vez por cuenta: dos pestañas no comparten la sesión
    a la vez ni abren sesiones paralelas contra Zajuna."""
    with _registry_lock:
        return _account_locks.setdefault(_account_key(config), threading.Lock())


def _shared_client(config: ZajunaConfig) -> ZajunaClient:
    """Cliente autenticado de la cuenta, reutilizado mientras siga en uso.

    Debe llamarse con el lock de la cuenta tomado.
    """
    key = _account_key(config)
    now = time.monotonic()
    cached = _sessions.get(key)
    if cached is not None and now - cached[1] < _SESSION_IDLE_TTL:
        _sessions[key] = (cached[0], now)
        return cached[0]
    try:
        auth = AuthManager(config)
        client = ZajunaClient(auth, config)
        auth.login()
    except Exception as e:
        _sessions.pop(key, None)
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo iniciar sesión en Zajuna: {e}",
        ) from e
    _sessions[key] = (client, now)
    return client


@router.get("/{ficha}/assignments", response_model=AssignmentMappingResponse)
def get_assignments(ficha: str):
    """Get the assignment mapping (item_id <-> cmid) for a ficha.

    Built during sync from the assignments + forum index pages.
    """
    data = load_assignments(ficha)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No assignment mapping found for ficha {ficha}. Run sync first.",
        )
    return AssignmentMappingResponse(
        ficha=data["ficha"],
        course_id=data["course_id"],
        updated_at=data["updated_at"],
        assignments=[
            AssignmentMappingItem(
                name=a["name"],
                cmid=a["cmid"],
                item_id=a.get("item_id"),
                module_type=a.get("module_type", "assign"),
            )
            for a in data["assignments"]
        ],
    )


@router.post("/{ficha}/pending-grading", response_model=PendingGradingResponse)
def check_pending_grading(
    ficha: str,
    body: PendingGradingRequest,
    config: ZajunaConfig = Depends(get_config),
    snapshot: dict = Depends(get_snapshot),
):
    """Check pending grading counts for selected evidences (on-demand scraping).

    Handles both assignments and forums:
    - Assignments: fetch /mod/assign/view.php → parse summary table
    - Forums: fetch forum view → list discussions → check each for ungraded posts
    """
    # 1. Load assignment mapping
    data = load_assignments(ficha)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No assignment mapping found for ficha {ficha}. Run sync first.",
        )

    # 2. Build item_id -> assignment lookup
    assignment_map: dict[int, dict] = {}
    for a in data["assignments"]:
        if a.get("item_id") is not None:
            assignment_map[a["item_id"]] = a

    # 3. Scrape on-demand con la sesión compartida de la cuenta. Los
    # cuestionarios salen del snapshot: no hace falta entrar a Zajuna.
    needs_zajuna = any(
        assignment_map[i].get("module_type", "assign") != "quiz"
        for i in body.item_ids
        if i in assignment_map
    )
    with _account_lock(config):
        client = _shared_client(config) if needs_zajuna else None
        results = [
            _check_item(client, snapshot, ficha, item_id, assignment_map.get(item_id))
            for item_id in body.item_ids
        ]

    return PendingGradingResponse(
        ficha=ficha,
        results=results,
        checked_at=datetime.now().isoformat(),
    )


def _check_item(
    client: ZajunaClient | None,
    snapshot: dict,
    ficha: str,
    item_id: int,
    assignment: dict | None,
) -> PendingGradingResult:
    """Pendientes de una evidencia. Nunca lanza: un fallo de Zajuna queda
    como `error` de esa fila y la consulta de las demás sigue."""
    if assignment is None:
        return PendingGradingResult(
            item_id=item_id,
            error="No cmid mapping found for this evidence",
        )

    cmid = assignment["cmid"]
    module_type = assignment.get("module_type", "assign")

    if module_type == "quiz":
        # Quizzes are auto-graded by Moodle — pull stats from grader report
        approved, disapproved, pending = _get_quiz_grade_counts(
            snapshot, ficha, item_id
        )
        return PendingGradingResult(
            item_id=item_id,
            cmid=cmid,
            name=assignment["name"],
            module_type="quiz",
            participants=approved + disapproved + pending,
            submitted=approved + disapproved,
            needs_grading=0,
            quiz_approved=approved,
            quiz_disapproved=disapproved,
            quiz_pending=pending,
        )

    try:
        if module_type == "forum":
            return _check_forum_pending(client, item_id, cmid, assignment["name"])
        return _check_assign_pending(client, item_id, cmid, assignment["name"])
    except Exception as e:  # noqa: BLE001 — una fila caída no tumba la consulta
        logger.exception("Failed to check item %d (cmid %d)", item_id, cmid)
        return PendingGradingResult(
            item_id=item_id, cmid=cmid, name=assignment["name"],
            module_type=module_type, error=f"Error inesperado: {e}",
        )


def _get_quiz_grade_counts(
    snapshot: dict, ficha: str, item_id: int
) -> tuple[int, int, int]:
    """Get A/D/- counts for a quiz evidence from the grader snapshot.

    Returns:
        Tuple of (approved, disapproved, pending) counts.
    """
    try:
        for course in snapshot.get("courses", []):
            if course.get("ficha") != ficha:
                continue
            approved = 0
            disapproved = 0
            pending = 0
            for student in course.get("students", []):
                grade = student.get("grades", {}).get(str(item_id))
                if grade is None:
                    pending += 1
                elif grade.get("value") == "A":
                    approved += 1
                elif grade.get("value") == "D":
                    disapproved += 1
                else:
                    pending += 1
            return approved, disapproved, pending
    except Exception as e:
        logger.warning("Failed to get quiz grades for item %d: %s", item_id, e)
    return 0, 0, 0


def _list_pending_students(client: ZajunaClient, cmid: int) -> list[GradingWaitingStudent]:
    """Apprentices with a submission sent for grading and not graded yet.

    Same rule the downloader uses, so this list matches what gets
    downloaded. A failure here keeps the counts and returns no names.
    """
    try:
        html = client.fetch_submissions_list(cmid)
        page = parse_submissions_page(html, cmid)
    except (FetchError, ParseError) as e:
        logger.warning("Failed to list pending students for cmid=%d: %s", cmid, e)
        return []
    return [
        GradingWaitingStudent(
            user_id=e.user_id,
            full_name=e.full_name,
            last_modified=e.last_modified,
            file_count=len(e.file_urls),
        )
        for e in page.entries
        if e.status == "Enviado para calificar" and not e.is_graded
    ]


def _check_assign_pending(
    client: ZajunaClient, item_id: int, cmid: int, name: str,
) -> PendingGradingResult:
    """Check pending grading for an assignment.

    Counts come from Zajuna's own summary table. Only when something is
    pending we also read the submissions list to name who is waiting.
    """
    try:
        html = client.fetch_assignment_detail(cmid)
        info = parse_assignment_detail(html, cmid)
        pending_students = (
            _list_pending_students(client, cmid) if info.needs_grading > 0 else []
        )
        return PendingGradingResult(
            item_id=item_id,
            cmid=cmid,
            name=name,
            module_type="assign",
            participants=info.participants,
            submitted=info.submitted,
            needs_grading=info.needs_grading,
            drafts=info.drafts,
            pending_students=pending_students,
        )
    except (FetchError, ParseError) as e:
        logger.warning("Failed to check assignment cmid=%d: %s", cmid, e)
        return PendingGradingResult(
            item_id=item_id, cmid=cmid, name=name,
            module_type="assign", error=str(e),
        )


def _check_forum_pending(
    client: ZajunaClient, item_id: int, forum_id: int, name: str,
) -> PendingGradingResult:
    """Check pending grading for a forum.

    Flow:
    1. Fetch forum view → get discussion list
    2. For each discussion → count ungraded posts
    3. Sum totals across all discussions
    """
    try:
        # 1. Get discussion list
        view_html = client.fetch_forum_view(forum_id)
        discussions = parse_forum_discussions(view_html, forum_id)

        total_posts = 0
        total_graded = 0
        total_ungraded = 0

        # 2. Check each discussion; los hilos que fallen se reintentan una
        # vez al final (Zajuna suele fallar por ratos, no siempre en el mismo)
        pending = list(discussions)
        last_error: Exception | None = None
        for _round in range(2):
            failed = []
            for disc in pending:
                try:
                    disc_html = client.fetch_forum_discussion(disc.discussion_id)
                    info = parse_forum_posts_grading(disc_html, disc.discussion_id)
                except (FetchError, ParseError) as e:
                    logger.warning(
                        "Failed to check discussion %d: %s",
                        disc.discussion_id, e,
                    )
                    failed.append(disc)
                    last_error = e
                    continue
                total_posts += info.total_posts
                total_graded += info.graded_posts
                total_ungraded += info.ungraded_posts
            pending = failed
            if not pending:
                break

        if pending:
            # Contar solo parte del foro daría un "por calificar" falso
            return PendingGradingResult(
                item_id=item_id, cmid=forum_id, name=name, module_type="forum",
                total_discussions=len(discussions),
                error=(
                    f"No se pudieron revisar {len(pending)} de {len(discussions)} "
                    f"hilos del foro: {last_error}"
                ),
            )

        return PendingGradingResult(
            item_id=item_id,
            cmid=forum_id,
            name=name,
            module_type="forum",
            participants=total_posts,      # Total posts with rating form
            submitted=total_graded,        # Posts already graded
            needs_grading=total_ungraded,  # Posts without grade
            total_discussions=len(discussions),
        )

    except (FetchError, ParseError) as e:
        logger.warning("Failed to check forum %d: %s", forum_id, e)
        return PendingGradingResult(
            item_id=item_id, cmid=forum_id, name=name,
            module_type="forum", error=str(e),
        )


# ── Submission status (per-student detail) ──────────────────────────────


class SubmissionStatusRequest(BaseModel):
    """Request body for checking submission status per student."""
    item_ids: list[int]
    force: bool = False  # Force re-fetch from Zajuna (ignore cache)


class SubmissionStatusResponse(BaseModel):
    """Response with set of submitted-but-ungraded cells."""
    ficha: str
    # List of "item_id:user_id" strings for cells that have submissions pending grading
    pending_cells: list[str]
    checked_count: int
    checked_at: str
    from_cache: bool = False


def _cache_path(ficha: str) -> Path:
    """Return the cache file path for submission status."""
    from src.config import SUBMISSION_STATUS_DIR
    from src.store.instructor_scope import scoped_dir
    return scoped_dir(SUBMISSION_STATUS_DIR) / f"{ficha}.json"


def _load_cache(ficha: str) -> dict | None:
    """Load cached submission status. Returns None if not found."""
    path = _cache_path(ficha)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(ficha: str, pending_cells: list[str], checked_count: int) -> str:
    """Save submission status to cache. Returns the checked_at timestamp."""
    _cache_path(ficha).parent.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now().isoformat()
    data = {
        "ficha": ficha,
        "pending_cells": pending_cells,
        "checked_count": checked_count,
        "checked_at": checked_at,
    }
    _cache_path(ficha).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return checked_at


@router.post("/{ficha}/submission-status", response_model=SubmissionStatusResponse)
async def check_submission_status(
    ficha: str,
    body: SubmissionStatusRequest,
    config: ZajunaConfig = Depends(get_config),
):
    """Check which students have submitted but ungraded work for each evidence.

    Returns cached results if available (instant). Use force=True to re-fetch
    from Zajuna (slow: login + delays por evidencia — corre en el pool
    dedicado de Zajuna para no ocupar los hilos de la API).
    """
    # 1. Return cache if available and not forced
    if not body.force:
        cached = _load_cache(ficha)
        if cached is not None:
            logger.info("Returning cached submission status for ficha %s", ficha)
            return SubmissionStatusResponse(
                ficha=ficha,
                pending_cells=cached["pending_cells"],
                checked_count=cached["checked_count"],
                checked_at=cached["checked_at"],
                from_cache=True,
            )

    # 2. Load assignment mapping
    data = load_assignments(ficha)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No assignment mapping found for ficha {ficha}. Run sync first.",
        )

    # Build item_id -> assignment lookup (assignments only, not forums)
    assignment_map: dict[int, dict] = {}
    for a in data["assignments"]:
        if a.get("item_id") is not None and a.get("module_type", "assign") == "assign":
            assignment_map[a["item_id"]] = a

    # 3. Authenticate and scrape (bloqueante → pool dedicado de Zajuna)
    def _scrape_live() -> tuple[list[str], int]:
        try:
            auth = AuthManager(config)
            client = ZajunaClient(auth, config)
            auth.login()
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to authenticate with Zajuna: {e}",
            ) from e

        cells: list[str] = []
        done = 0
        for item_id in body.item_ids:
            assignment = assignment_map.get(item_id)
            if assignment is None:
                continue

            cmid = assignment["cmid"]
            try:
                html = client.fetch_submissions_list(cmid)
                page = parse_submissions_page(html, cmid)
                done += 1

                for entry in page.entries:
                    # "Enviado para calificar" + not graded = pending (yellow)
                    if entry.status == "Enviado para calificar" and not entry.is_graded:
                        cells.append(f"{item_id}:{entry.user_id}")

                # Human delay between requests
                time.sleep(2)
            except (FetchError, ParseError) as e:
                logger.warning("Failed to fetch submissions for cmid=%d: %s", cmid, e)
        return cells, done

    pending_cells, checked = await run_in_zajuna_pool(_scrape_live)

    # 4. Cache results
    checked_at = _save_cache(ficha, pending_cells, checked)

    return SubmissionStatusResponse(
        ficha=ficha,
        pending_cells=pending_cells,
        checked_count=checked,
        checked_at=checked_at,
    )
