"""Main entry point for the Zajuna scraper (CLI)."""
from __future__ import annotations

import json
import logging
import sys
import time

from src.auth.manager import AuthError
from src.config import LOGS_DIR, ZajunaConfig, instructor_data_dir
from src.scraper.runner import scrape_courses
from src.store import tracked_courses_store as tracked_store
from src.store import zajuna_accounts_store as vault


def setup_logging(log_level: str) -> None:
    """Configure logging to both console and file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    fmt = "[%(asctime)s] %(levelname)-5s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    file_handler = logging.FileHandler(
        LOGS_DIR / "scraper.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root.addHandler(console)
    root.addHandler(file_handler)

    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# Pausa entre instructores para mantener el patron de trafico humano
STAGGER_SECONDS = 90


def _course_ids_for(cmm_user_id: str, config: ZajunaConfig) -> list[int]:
    """Cursos a refrescar para un instructor.

    Prioridad: su registro de cursos seguidos (courses.json), luego los
    cursos de su ultimo snapshot y, mientras no tenga ninguno, los
    course_ids del .env (legado).
    """
    tracked = tracked_store.tracked_course_ids(cmm_user_id)
    if tracked is not None:
        return tracked

    latest = instructor_data_dir(cmm_user_id) / "latest.json"
    if latest.exists():
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            ids = [c["course_id"] for c in data.get("courses", [])]
            if ids:
                return ids
        except (json.JSONDecodeError, OSError):
            pass
    return config.course_ids


def run_scraper() -> None:
    """Execute the full scraping pipeline from CLI (cron).

    Multi-instructor: itera cada cuenta Zajuna conectada (vault) y
    scrapea sus fichas con sus credenciales, escalonado. Sin cuentas
    conectadas cae al comportamiento legado (.env, layout global).
    """
    config = ZajunaConfig()
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    user_ids = vault.list_connected_user_ids()

    logger.info("=" * 60)
    logger.info("Zajuna Monitor - Starting scraper run")
    logger.info(
        "Instructores con cuenta conectada: %s",
        user_ids or "(ninguno; modo legado .env)",
    )
    logger.info("=" * 60)

    if not user_ids:
        try:
            scrape_courses(config, config.course_ids)
        except AuthError as e:
            logger.error("Authentication failed: %s", e)
            sys.exit(1)
        except Exception as e:
            logger.error("Scraper failed: %s", e)
            sys.exit(1)
        return

    failures = 0
    for i, user_id in enumerate(user_ids):
        if i > 0:
            logger.info("Pausa de %ds antes del siguiente instructor...", STAGGER_SECONDS)
            time.sleep(STAGGER_SECONDS)

        course_ids = _course_ids_for(user_id, config)
        logger.info(
            "Instructor CMM %s: scrapeando %d cursos", user_id, len(course_ids)
        )
        try:
            scrape_courses(config, course_ids, cmm_user_id=user_id)
        except AuthError as e:
            # scrape_courses ya marco la cuenta como invalida
            logger.error("Instructor CMM %s: autenticacion fallida: %s", user_id, e)
            failures += 1
        except Exception as e:
            logger.error("Instructor CMM %s: scrape fallido: %s", user_id, e)
            failures += 1

    if failures == len(user_ids):
        logger.error("Todos los scrapes fallaron (%d/%d)", failures, len(user_ids))
        sys.exit(1)
    logger.info("Scrapes completados: %d ok, %d fallidos", len(user_ids) - failures, failures)


if __name__ == "__main__":
    run_scraper()
