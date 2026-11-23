"""Vault de cuentas Zajuna conectadas por instructor.

Guarda las credenciales de Zajuna de cada instructor (identificado por su
user_id del Sistema CMM) con la contraseña cifrada en reposo (Fernet /
AES-128-CBC + HMAC). El scraper las usa para trabajar en nombre del
instructor; nunca se exponen al frontend.

Clave de cifrado (en orden de prioridad):
1. Env var ZAJUNA_CRED_KEY (obligatoria en producción — clave Fernet).
2. Archivo local data/.cred_key (se autogenera en desarrollo).

Archivo de datos: data/zajuna_accounts.json
    {"<cmm_user_id>": {"type_document", "document", "password_enc",
                        "connected_at", "status", "last_validated_at"}}
status: "ok" | "invalid" (Zajuna rechazó las credenciales en un scrape).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

ACCOUNTS_PATH: Path = DATA_DIR / "zajuna_accounts.json"
KEY_PATH: Path = DATA_DIR / ".cred_key"

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    key = os.environ.get("ZAJUNA_CRED_KEY", "").strip()
    if not key:
        if KEY_PATH.exists():
            key = KEY_PATH.read_text(encoding="utf-8").strip()
        else:
            key = Fernet.generate_key().decode()
            KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
            KEY_PATH.write_text(key, encoding="utf-8")
            logger.warning(
                "ZAJUNA_CRED_KEY no configurada: se generó una clave local en %s. "
                "En producción define ZAJUNA_CRED_KEY como variable de entorno.",
                KEY_PATH,
            )
    _fernet = Fernet(key.encode())
    return _fernet


# Cache por mtime: get_config() consulta el vault en CADA request autenticado;
# sin esto, cada petición pagaba una lectura de disco + json.loads (y el
# descifrado Fernet en get_any_account). El archivo solo cambia al
# conectar/desconectar una cuenta.
_load_cache: tuple[float, dict[str, dict]] | None = None
_creds_cache: tuple[float, tuple[str, dict] | None] | None = None


def _file_mtime() -> float | None:
    try:
        return ACCOUNTS_PATH.stat().st_mtime
    except OSError:
        return None


def _load() -> dict[str, dict]:
    global _load_cache
    mtime = _file_mtime()
    if mtime is None:
        return {}
    if _load_cache is not None and _load_cache[0] == mtime:
        return _load_cache[1]
    try:
        data = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("No se pudo leer %s: %s", ACCOUNTS_PATH, exc)
        return {}
    _load_cache = (mtime, data)
    return data


def _save(accounts: dict[str, dict]) -> None:
    global _load_cache, _creds_cache
    ACCOUNTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_PATH.write_text(
        json.dumps(accounts, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # Invalidar caches (no confiar solo en la resolución del mtime)
    _load_cache = None
    _creds_cache = None


def get_account_record(user_id: str) -> dict | None:
    """Registro tal como se persiste (contraseña cifrada). Para status/UI."""
    return _load().get(str(user_id))


def get_account_credentials(user_id: str) -> dict | None:
    """Credenciales descifradas: {type_document, document, password}."""
    record = get_account_record(user_id)
    if record is None:
        return None
    password = _get_fernet().decrypt(record["password_enc"].encode()).decode()
    return {
        "type_document": record["type_document"],
        "document": record["document"],
        "password": password,
    }


def save_account(user_id: str, type_document: str, document: str, password: str) -> dict:
    """Cifra y persiste las credenciales (ya validadas contra Zajuna)."""
    accounts = _load()
    now = datetime.now(UTC).isoformat()
    accounts[str(user_id)] = {
        "type_document": type_document,
        "document": document,
        "password_enc": _get_fernet().encrypt(password.encode()).decode(),
        "connected_at": accounts.get(str(user_id), {}).get("connected_at", now),
        "status": "ok",
        "last_validated_at": now,
    }
    _save(accounts)
    logger.info("Cuenta Zajuna conectada para usuario CMM %s (doc %s****)", user_id, document[:4])
    return accounts[str(user_id)]


def delete_account(user_id: str) -> bool:
    accounts = _load()
    if str(user_id) not in accounts:
        return False
    del accounts[str(user_id)]
    _save(accounts)
    logger.info("Cuenta Zajuna desconectada para usuario CMM %s", user_id)
    return True


def mark_status(user_id: str, status: str) -> None:
    """Marca el estado de las credenciales (p. ej. 'invalid' si Zajuna rechaza)."""
    accounts = _load()
    record = accounts.get(str(user_id))
    if record is not None:
        record["status"] = status
        _save(accounts)


def list_connected_user_ids() -> list[str]:
    """user_ids CMM con cuenta Zajuna conectada y credenciales vigentes."""
    return [
        user_id
        for user_id, record in _load().items()
        if record.get("status") == "ok"
    ]


def get_any_account() -> tuple[str, dict] | None:
    """(user_id, credenciales descifradas) de la única/primera cuenta conectada.

    Cacheado por mtime: el Fernet.decrypt solo corre cuando el archivo
    cambia, no en cada request. Transitorio del paso 2 (una sola cuenta
    manda para todo el scraping); el paso 3 (multi-instructor) reemplaza
    esto por resolución por usuario.
    """
    global _creds_cache
    mtime = _file_mtime()
    if mtime is not None and _creds_cache is not None and _creds_cache[0] == mtime:
        return _creds_cache[1]

    result: tuple[str, dict] | None = None
    accounts = _load()
    for user_id, record in accounts.items():
        if record.get("status") == "ok":
            creds = get_account_credentials(user_id)
            if creds:
                result = (user_id, creds)
                break

    if mtime is not None:
        _creds_cache = (mtime, result)
    return result

