"""Shared dependencies for the Zajuna Monitor API."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from src.config import DATA_DIR, ZajunaConfig, instructor_data_dir
from src.store import tracked_courses_store as tracked_store

logger = logging.getLogger(__name__)

# --- Config singleton ---

_config: ZajunaConfig | None = None


def get_base_config() -> ZajunaConfig:
    """Config del .env, sin tocar las credenciales (api_key, URLs, demoras)."""
    global _config
    if _config is None:
        _config = ZajunaConfig()
    return _config


def get_config(request: Request) -> ZajunaConfig:
    """Config con la cuenta Zajuna DEL instructor autenticado (vault cifrado).

    Nunca se usa la cuenta de otro instructor: sin cuenta conectada, 409.
    Sin usuario (procesos internos) quedan las credenciales del .env.
    """
    config = get_base_config()
    user = getattr(request.state, "user", None)
    if not user or user.get("id") is None:
        return config
    # Import tardío para evitar ciclo (el store importa src.config)
    from src.store import zajuna_accounts_store as vault

    creds = vault.get_account_credentials(str(user["id"]))
    if creds is None:
        raise HTTPException(
            status_code=409,
            detail="Conecta tu cuenta de Zajuna en tu perfil para usar esta opción.",
        )
    return config.model_copy(
        update={
            "zajuna_type_document": creds["type_document"],
            "zajuna_document": creds["document"],
            "zajuna_password": creds["password"],
        }
    )


# --- Snapshot loader with mtime caching (por path: soporta multi-instructor) ---

_snapshot_cache: dict[str, tuple[float, dict]] = {}
_snapshot_path: Path = DATA_DIR / "latest.json"


def get_snapshot_path() -> Path:
    return _snapshot_path


def snapshot_path_for(request: Request | None) -> Path:
    """Path del snapshot del instructor autenticado.

    Un instructor sin su primer scrape (data/instructors/<id>/latest.json)
    no ve el snapshot global, que tiene los grupos de otro instructor:
    recibe 503 hasta sincronizar. El global queda para procesos sin usuario
    (arranque, scraper por consola).
    """
    if request is not None:
        user = getattr(request.state, "user", None)
        if user and user.get("id") is not None:
            return instructor_data_dir(user["id"]) / "latest.json"
    return _snapshot_path


def load_snapshot(path: Path | None = None) -> dict:
    """Load snapshot from disk, using an mtime cache keyed by path."""
    target = path or _snapshot_path

    if not target.exists():
        raise HTTPException(
            status_code=503,
            detail="No snapshot available. Run the scraper first.",
        )

    key = str(target)
    current_mtime = target.stat().st_mtime

    cached = _snapshot_cache.get(key)
    if cached is not None and cached[0] == current_mtime:
        return cached[1]

    logger.info("Loading snapshot from %s", target)
    data = json.loads(target.read_text(encoding="utf-8"))
    _snapshot_cache[key] = (current_mtime, data)
    logger.info("Snapshot loaded: %d courses", len(data.get("courses", [])))
    return data


def visible_snapshot(data: dict, tracked_ids: set[int] | None) -> dict:
    """Solo los cursos que el instructor sigue.

    Quitar un grupo en "Agregar grupo" no borra nada: sus datos siguen en el
    snapshot y en los stores por ficha, y vuelven si se agrega de nuevo.
    Sin registro de cursos (None) se ve todo, como antes.
    """
    if tracked_ids is None:
        return data

    def keep(items: list[dict]) -> list[dict]:
        return [item for item in items if item.get("course_id") in tracked_ids]

    return {
        **data,
        "courses": keep(data.get("courses", [])),
        "summaries": keep(data.get("summaries", [])),
        "participants": keep(data.get("participants", [])),
    }


def get_snapshot(request: Request) -> dict:
    """FastAPI dependency: snapshot del instructor autenticado (o global),
    limitado a los grupos que sigue."""
    data = load_snapshot(snapshot_path_for(request))
    user = getattr(request.state, "user", None)
    tracked = tracked_store.tracked_course_ids(user.get("id")) if user else None
    return visible_snapshot(data, set(tracked) if tracked is not None else None)


# --- API key auth ---

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    api_key: str | None = Security(_api_key_header),
    config: ZajunaConfig = Depends(get_base_config),
) -> str:
    """Validate the API key from X-API-Key header."""
    if not config.api_key or config.api_key == "change-this-to-a-secure-random-string":
        # API key not configured — allow all requests (dev mode)
        return "dev"

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if api_key != config.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key
