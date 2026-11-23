"""In-memory job manager for scraper runs: one job at a time per instructor.

Cada instructor sincroniza con su propia cuenta de Zajuna, así que el job de
uno no bloquea al de otro ni ve su progreso.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from src.config import ZajunaConfig
from src.scraper.runner import scrape_courses

logger = logging.getLogger(__name__)


@dataclass
class ScraperStep:
    """A single step in the scraping pipeline."""

    label: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"


@dataclass
class ScraperJob:
    """State of a scraper run."""

    job_id: str
    status: str = "running"  # "running" | "completed" | "failed"
    started_at: str = ""
    finished_at: str | None = None
    progress: str = ""
    courses_total: int = 0
    courses_done: int = 0
    error: str | None = None
    duration_seconds: float | None = None
    steps: list[ScraperStep] = field(default_factory=list)


# --- Estado por instructor ---

_jobs: dict[str, ScraperJob] = {}
_lock = threading.Lock()


def _key(cmm_user_id: str | None) -> str:
    return "" if cmm_user_id is None else str(cmm_user_id)


def is_running(cmm_user_id: str | None = None) -> bool:
    """¿El instructor tiene un job en curso?"""
    with _lock:
        job = _jobs.get(_key(cmm_user_id))
        return job is not None and job.status == "running"


def get_current_job(cmm_user_id: str | None = None) -> ScraperJob | None:
    """Job en curso o último job del instructor."""
    with _lock:
        return _jobs.get(_key(cmm_user_id))


def start_job(
    config: ZajunaConfig,
    course_ids: list[int],
    cmm_user_id: str | None = None,
) -> ScraperJob:
    """Launch a scraper job in a background thread.

    Raises:
        RuntimeError: If a job is already running.
    """
    with _lock:
        current = _jobs.get(_key(cmm_user_id))
        if current is not None and current.status == "running":
            raise RuntimeError("A scraper job is already running")

        job = ScraperJob(
            job_id=uuid.uuid4().hex[:12],
            status="running",
            started_at=datetime.now().isoformat(),
            courses_total=len(course_ids),
            progress="Iniciando...",
            steps=_build_steps(course_ids, cmm_user_id),
        )
        _jobs[_key(cmm_user_id)] = job

    # scrape_courses fija al instructor: sus datos por ficha van a su carpeta.
    threading.Thread(
        target=_run_job,
        args=(job, config, course_ids, cmm_user_id),
        daemon=True,
    ).start()
    return job


def _build_steps(
    course_ids: list[int], cmm_user_id: str | None = None
) -> list[ScraperStep]:
    """Pre-build the step list for progress tracking."""
    steps = [ScraperStep(label="Autenticacion")]
    for cid in course_ids:
        ficha = _resolve_ficha(cid, cmm_user_id)
        steps.append(ScraperStep(label=f"Ficha {ficha} \u2014 calificaciones"))
        steps.append(ScraperStep(label=f"Ficha {ficha} \u2014 participantes"))
        steps.append(ScraperStep(label=f"Ficha {ficha} \u2014 actividades"))
    return steps


def _resolve_ficha(course_id: int, cmm_user_id: str | None = None) -> str:
    """Try to get ficha label from the instructor's snapshot (global sin instructor)."""
    import json

    from src.config import DATA_DIR, instructor_data_dir

    latest = DATA_DIR / "latest.json"
    if cmm_user_id is not None:
        latest = instructor_data_dir(cmm_user_id) / "latest.json"
    if latest.exists():
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            for course in data.get("courses", []):
                if course.get("course_id") == course_id:
                    return course.get("ficha", str(course_id))
        except Exception:
            pass
    return str(course_id)


def _run_job(
    job: ScraperJob,
    config: ZajunaConfig,
    course_ids: list[int],
    cmm_user_id: str | None = None,
) -> None:
    """Background thread: execute scraper and update job state."""
    start = time.monotonic()
    step_idx = 0  # tracks which step we're on

    def on_progress(msg: str, done: int, total: int) -> None:
        nonlocal step_idx
        with _lock:
            job.progress = msg
            job.courses_done = done

            # Update step statuses based on progress messages
            _update_steps(job, msg, done)

    try:
        scrape_courses(
            config, course_ids, on_progress=on_progress, cmm_user_id=cmm_user_id
        )

        with _lock:
            job.status = "completed"
            job.courses_done = job.courses_total
            job.progress = "Completado"
            # Mark all steps as completed
            for step in job.steps:
                if step.status != "failed":
                    step.status = "completed"

    except Exception as e:
        logger.exception("Scraper job %s failed", job.job_id)
        with _lock:
            job.status = "failed"
            job.error = str(e)
            job.progress = f"Error: {e}"
            # Mark current running step as failed
            for step in job.steps:
                if step.status == "running":
                    step.status = "failed"
                    break

    finally:
        duration = time.monotonic() - start
        with _lock:
            job.finished_at = datetime.now().isoformat()
            job.duration_seconds = round(duration, 1)


def _update_steps(job: ScraperJob, msg: str, courses_done: int) -> None:
    """Update step statuses based on progress callback messages."""
    if not job.steps:
        return

    if msg == "Completado":
        for step in job.steps:
            if step.status != "failed":
                step.status = "completed"
        return

    # Determine step index from courses_done and message content
    # Steps per course: calificaciones (0), participantes (1), actividades (2)
    if msg.startswith("Autenticando"):
        current_idx = 0
    else:
        if "participantes" in msg:
            step_offset = 1
        elif "actividades" in msg:
            step_offset = 2
        else:
            step_offset = 0  # calificaciones
        current_idx = 1 + courses_done * 3 + step_offset

    if current_idx < len(job.steps):
        # Update label with real ficha name (replaces courseId with ficha)
        job.steps[current_idx].label = msg
        # Mark all previous steps as completed
        for i in range(current_idx):
            if job.steps[i].status != "failed":
                job.steps[i].status = "completed"
        # Mark current as running
        job.steps[current_idx].status = "running"
        # Mark remaining as pending
        for i in range(current_idx + 1, len(job.steps)):
            if job.steps[i].status not in ("completed", "failed"):
                job.steps[i].status = "pending"
