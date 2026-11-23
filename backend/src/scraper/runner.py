"""Reusable scraping logic, callable from CLI or API."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from src.auth.manager import AuthError, AuthManager
from src.client.zajuna import FetchError, ZajunaClient
from src.config import DATA_DIR, ZajunaConfig
from src.models.schemas import ScraperSnapshot
from src.parsers.assignments_index import match_assignments_to_evidences, parse_assignments_index
from src.parsers.forum_index import match_forums_to_evidences, parse_forum_index
from src.parsers.grader import GraderParser, ParseError
from src.parsers.participants import ParticipantsParser
from src.parsers.quiz_index import match_quizzes_to_evidences, parse_quiz_index
from src.store import tracked_courses_store as tracked_store
from src.store.assignments_store import save_assignments
from src.store.instructor_scope import as_instructor
from src.store.json_store import save_snapshot

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], None]


def scrape_courses(
    config: ZajunaConfig,
    course_ids: list[int],
    on_progress: ProgressCallback | None = None,
    cmm_user_id: str | None = None,
) -> dict:
    """Scrape con el instructor fijado: el mapeo de actividades por ficha
    (assignments_store) se guarda en su carpeta. Ver ``_scrape_courses``."""
    with as_instructor(cmm_user_id):
        return _scrape_courses(config, course_ids, on_progress, cmm_user_id)


def _scrape_courses(
    config: ZajunaConfig,
    course_ids: list[int],
    on_progress: ProgressCallback | None = None,
    cmm_user_id: str | None = None,
) -> dict:
    """Scrape specific courses and merge into the existing snapshot.

    Args:
        config: Zajuna configuration with credentials.
        course_ids: List of Moodle course IDs to scrape.
        on_progress: Optional callback(step_label, courses_done, courses_total).
        cmm_user_id: Si se pasa, usa las credenciales del vault de ESE
            instructor y escribe el snapshot en su directorio particionado
            (data/instructors/<id>/). Sin él, comportamiento legado:
            primera cuenta del vault (o .env) y layout global.

    Returns:
        The full merged snapshot as a dict.

    Raises:
        AuthError: If authentication fails.
    """
    start_time = time.monotonic()
    total = len(course_ids)

    def _progress(msg: str, done: int = 0) -> None:
        if on_progress:
            on_progress(msg, done, total)

    # --- Authenticate ---
    # La cuenta Zajuna conectada (vault cifrado) tiene prioridad sobre el .env,
    # también cuando este runner corre desde el cron/CLI sin pasar por la API.
    from src.store import zajuna_accounts_store as vault

    vault_user_id: str | None = None
    vault_creds = None
    if cmm_user_id is not None:
        vault_creds = vault.get_account_credentials(cmm_user_id)
        if vault_creds is None:
            raise AuthError(
                f"El instructor CMM {cmm_user_id} no tiene cuenta Zajuna conectada"
            )
        vault_user_id = cmm_user_id
    else:
        vault_result = vault.get_any_account()
        if vault_result is not None:
            vault_user_id, vault_creds = vault_result
    if vault_creds is not None:
        config = config.model_copy(
            update={
                "zajuna_type_document": vault_creds["type_document"],
                "zajuna_document": vault_creds["document"],
                "zajuna_password": vault_creds["password"],
            }
        )

    from src.config import instructor_data_dir

    base_dir = instructor_data_dir(cmm_user_id) if cmm_user_id is not None else None
    latest_path = (base_dir or DATA_DIR) / "latest.json"

    _progress("Autenticando...", 0)
    auth = AuthManager(config)
    client = ZajunaClient(auth, config)
    try:
        auth.login()
    except AuthError:
        # Zajuna rechazó las credenciales del vault: marcar caducas para que
        # el dashboard avise al instructor que debe actualizarlas.
        if vault_user_id is not None:
            vault.mark_status(vault_user_id, "invalid")
            logger.error(
                "Credenciales Zajuna del vault rechazadas (usuario CMM %s); "
                "marcadas como caducas.", vault_user_id,
            )
        raise
    logger.info("Authenticated as user %s", auth.user_id)

    # --- Build partial snapshot ---
    snapshot = ScraperSnapshot(
        timestamp=datetime.now(),
        instructor_id=auth.user_id or 0,
    )

    for i, course_id in enumerate(course_ids):
        # Ficha seg\u00fan el registro del instructor (fuente de verdad para cursos
        # reci\u00e9n agregados o cuyo t\u00edtulo no trae "(NNNNNNN)").
        tracked_ficha = tracked_store.ficha_for_course(cmm_user_id, course_id)
        ficha_label = tracked_ficha or _ficha_for_course(course_id, latest_path)
        report = None  # Track grader result for assignments matching

        # Grader
        _progress(f"Ficha {ficha_label} \u2014 calificaciones", i)
        try:
            html = client.fetch_grader(course_id)
            parser = GraderParser(html, course_id)
            report = parser.parse()
            if not report.ficha and tracked_ficha:
                logger.warning(
                    "Grader del curso %d sin ficha en el t\u00edtulo; se usa %s del registro",
                    course_id, tracked_ficha,
                )
                report.ficha = tracked_ficha
            summary = parser.compute_summary(report)
            snapshot.courses.append(report)
            snapshot.summaries.append(summary)
            ficha_label = report.ficha
            logger.info("Grader OK: course %d (ficha %s)", course_id, ficha_label)
        except (FetchError, ParseError) as e:
            logger.error("Grader failed for course %d: %s", course_id, e)
            snapshot.errors.append({
                "course_id": course_id,
                "error": str(e),
                "type": type(e).__name__,
                "source": "grader",
            })

        # Participants
        _progress(f"Ficha {ficha_label} \u2014 participantes", i)
        try:
            participants_html = client.fetch_participants(course_id)
            participants_parser = ParticipantsParser(participants_html, course_id)
            course_participants = participants_parser.parse()
            if not course_participants.ficha and tracked_ficha:
                course_participants.ficha = tracked_ficha
            snapshot.participants.append(course_participants)
            logger.info(
                "Participants OK: course %d, %d participants",
                course_id,
                len(course_participants.participants),
            )
        except (FetchError, ParseError) as e:
            logger.error("Participants failed for course %d: %s", course_id, e)
            snapshot.errors.append({
                "course_id": course_id,
                "error": str(e),
                "type": type(e).__name__,
                "source": "participants",
            })

        # Activities: assignments, forums and quizzes index (item_id <-> cmid mapping)
        _progress(f"Ficha {ficha_label} \u2014 actividades", i)
        evidences = report.evidences if report else []
        combined_mapping: list[dict] = []

        # Assignments
        try:
            assignments_html = client.fetch_assignments_index(course_id)
            assignments = parse_assignments_index(assignments_html)
            assign_mapping = match_assignments_to_evidences(assignments, evidences)
            for entry in assign_mapping:
                entry["module_type"] = "assign"
            combined_mapping.extend(assign_mapping)
            logger.info(
                "Assignments OK: course %d, %d assignments mapped",
                course_id, len(assign_mapping),
            )
        except (FetchError, ParseError) as e:
            logger.warning("Assignments failed for course %d: %s", course_id, e)

        # Forums
        try:
            forum_html = client.fetch_forum_index(course_id)
            forums = parse_forum_index(forum_html)
            forum_mapping = match_forums_to_evidences(forums, evidences)
            combined_mapping.extend(forum_mapping)
            logger.info(
                "Forums OK: course %d, %d forums mapped",
                course_id, len(forum_mapping),
            )
        except (FetchError, ParseError) as e:
            logger.warning("Forums failed for course %d: %s", course_id, e)

        # Quizzes (auto-graded, marked as module_type="quiz")
        try:
            quiz_html = client.fetch_quiz_index(course_id)
            quizzes = parse_quiz_index(quiz_html)
            quiz_mapping = match_quizzes_to_evidences(quizzes, evidences)
            combined_mapping.extend(quiz_mapping)
            logger.info(
                "Quizzes OK: course %d, %d quizzes mapped",
                course_id, len(quiz_mapping),
            )
        except (FetchError, ParseError) as e:
            logger.warning("Quizzes failed for course %d: %s", course_id, e)

        # Save combined mapping
        if combined_mapping:
            save_assignments(ficha_label, course_id, combined_mapping)

    # --- Metadata ---
    duration = time.monotonic() - start_time
    snapshot.metadata = {
        "version": "1.0.0",
        "duration_seconds": round(duration, 1),
        "total_courses": len(snapshot.courses),
        "total_errors": len(snapshot.errors),
        "total_requests": client.request_count,
    }

    # --- Merge with existing snapshot ---
    merged = _merge_snapshot(snapshot, latest_path)

    # --- Save ---
    if merged.courses:
        save_snapshot(merged, base_dir=base_dir)
        _progress("Completado", total)
        logger.info("Scrape complete in %.1fs", duration)
    else:
        logger.error("No courses scraped. Snapshot not saved.")

    return _snapshot_to_dict(merged)


def _ficha_for_course(course_id: int, latest: Path) -> str:
    """Try to resolve ficha from existing snapshot, fallback to course_id."""
    if latest.exists():
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            for course in data.get("courses", []):
                if course.get("course_id") == course_id:
                    return course.get("ficha", str(course_id))
        except Exception:
            pass
    return str(course_id)


def _merge_snapshot(new: ScraperSnapshot, latest: Path) -> ScraperSnapshot:
    """Merge newly scraped data into existing snapshot, replacing updated courses."""
    if not latest.exists():
        return new

    try:
        existing = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return new

    scraped_ids = {c.course_id for c in new.courses}

    # Keep existing courses that were NOT re-scraped

    for course_data in existing.get("courses", []):
        if course_data["course_id"] not in scraped_ids:
            report = _dict_to_course_report(course_data)
            new.courses.append(report)

    for summary_data in existing.get("summaries", []):
        if summary_data["course_id"] not in scraped_ids:
            new.summaries.append(_dict_to_summary(summary_data))

    scraped_participant_ids = {p.course_id for p in new.participants}
    for part_data in existing.get("participants", []):
        if part_data["course_id"] not in scraped_participant_ids:
            new.participants.append(_dict_to_participants(part_data))

    return new


def _dict_to_course_report(d: dict):
    """Reconstruct CourseReport from dict."""
    from src.models.schemas import CourseReport, Evidence, GradeCell, GradeStatus, StudentRow

    evidences = [
        Evidence(item_id=e["item_id"], name=e["name"], category=e["category"])
        for e in d.get("evidences", [])
    ]
    students = []
    for s in d.get("students", []):
        grades = {}
        for k, g in s.get("grades", {}).items():
            grades[int(k)] = GradeCell(
                evidence_id=g["evidence_id"],
                value=GradeStatus(g["value"]),
                passed=g["passed"],
            )
        students.append(StudentRow(
            user_id=s["user_id"],
            full_name=s["full_name"],
            document=s["document"],
            email=s["email"],
            grades=grades,
        ))
    return CourseReport(
        course_id=d["course_id"],
        course_name=d["course_name"],
        ficha=d["ficha"],
        evidences=evidences,
        students=students,
    )


def _dict_to_summary(d: dict):
    """Reconstruct CourseSummary from dict."""
    from src.models.schemas import CourseSummary
    return CourseSummary(
        course_id=d["course_id"],
        ficha=d["ficha"],
        total_students=d["total_students"],
        total_evidences=d["total_evidences"],
        total_approved=d["total_approved"],
        total_disapproved=d["total_disapproved"],
        total_pending=d["total_pending"],
        completion_percentage=d["completion_percentage"],
        pending_by_evidence=d.get("pending_by_evidence", {}),
    )


def _dict_to_participants(d: dict):
    """Reconstruct CourseParticipants from dict."""
    from src.models.schemas import CourseParticipants, Participant, StudentStatus
    participants = []
    for p in d.get("participants", []):
        participants.append(Participant(
            user_id=p["user_id"],
            full_name=p["full_name"],
            document=p["document"],
            email=p["email"],
            role=p["role"],
            groups=p["groups"],
            last_access_raw=p["last_access_raw"],
            last_access_days=p["last_access_days"],
            status=StudentStatus(p["status"]),
        ))
    return CourseParticipants(
        course_id=d["course_id"],
        ficha=d["ficha"],
        participants=participants,
    )


def _snapshot_to_dict(snapshot: ScraperSnapshot) -> dict:
    """Convert snapshot to dict (same as what save_snapshot writes)."""
    from dataclasses import asdict

    from src.store.json_store import SnapshotEncoder
    raw = json.dumps(asdict(snapshot), cls=SnapshotEncoder, ensure_ascii=False)
    return json.loads(raw)
