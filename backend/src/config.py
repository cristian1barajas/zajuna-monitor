"""Application configuration using pydantic-settings."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Base paths relative to the backend/ directory
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
CRONOGRAMAS_DIR = DATA_DIR / "cronogramas"
DUE_PROCESS_DIR = DATA_DIR / "due_process"
RAP_MAPPINGS_DIR = DATA_DIR / "rap_mappings"
SOFIA_REPORTS_DIR = DATA_DIR / "sofia_reports"
INSTRUCTORS_DIR = DATA_DIR / "instructors"


def instructor_data_dir(cmm_user_id: str) -> Path:
    """Directorio de datos particionado por instructor (paso 3 multi-instructor)."""
    return INSTRUCTORS_DIR / str(cmm_user_id)

ASSIGNMENTS_DIR = DATA_DIR / "assignments"
SUBMISSION_STATUS_DIR = DATA_DIR / "submission_status"
NOVEDADES_DIR = DATA_DIR / "novedades"
SOPORTES_DIR = DATA_DIR / "soportes_llamados"
ACTAS_DIR = DATA_DIR / "actas_equipo_ejecutor"
FORUM_REPLIES_DIR = DATA_DIR / "forum_replies"
LOGS_DIR = BASE_DIR / "logs"


class ZajunaConfig(BaseSettings):
    """Configuration loaded from .env file or environment variables."""

    # Zajuna credentials
    zajuna_base_url: str = "https://zajuna.sena.edu.co"
    zajuna_type_document: str = "CC"
    zajuna_document: str
    zajuna_password: str

    # Courses to scrape (comma-separated in .env, parsed after init)
    zajuna_course_ids: str = ""

    # Scraper behavior
    min_delay: float = 2.0
    max_delay: float = 5.0
    request_timeout: int = 60

    # Logging
    log_level: str = "INFO"

    # API (Phase 2)
    api_key: str = ""
    # Solo local por defecto: en producción la API va detrás de Nginx.
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def course_ids(self) -> list[int]:
        """Parse comma-separated course IDs string to list[int]."""
        if not self.zajuna_course_ids:
            return []
        return [int(x.strip()) for x in self.zajuna_course_ids.split(",") if x.strip()]
