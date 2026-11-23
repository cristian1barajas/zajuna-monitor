"""Conexión de la cuenta Zajuna del instructor autenticado.

El instructor (autenticado vía JWT del Sistema CMM) registra sus
credenciales de Zajuna. Antes de guardar, se validan EN VIVO haciendo el
flujo de login real contra Zajuna (AuthManager); si Zajuna las rechaza,
no se persiste nada. La contraseña queda cifrada en reposo (vault).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_base_config
from src.api.executors import run_in_zajuna_pool
from src.auth.manager import AuthError, AuthManager, ZajunaUnavailableError
from src.config import ZajunaConfig
from src.store import zajuna_accounts_store as vault

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/zajuna-account", tags=["zajuna-account"])


class ConnectAccountRequest(BaseModel):
    type_document: str = Field(default="CC", pattern="^(CC|CE|TI|PEP)$")
    document: str = Field(min_length=4, max_length=20)
    password: str = Field(min_length=1)


class AccountStatusResponse(BaseModel):
    connected: bool
    type_document: str | None = None
    document_masked: str | None = None
    status: str | None = None
    connected_at: str | None = None
    last_validated_at: str | None = None


def _mask(document: str) -> str:
    if len(document) <= 4:
        return "****"
    return f"{document[:2]}{'*' * (len(document) - 4)}{document[-2:]}"


def _status_response(user_id: str) -> AccountStatusResponse:
    record = vault.get_account_record(user_id)
    if record is None:
        return AccountStatusResponse(connected=False)
    return AccountStatusResponse(
        connected=True,
        type_document=record["type_document"],
        document_masked=_mask(record["document"]),
        status=record.get("status", "ok"),
        connected_at=record.get("connected_at"),
        last_validated_at=record.get("last_validated_at"),
    )


@router.get("", response_model=AccountStatusResponse)
def get_account_status(request: Request) -> AccountStatusResponse:
    """Estado de la cuenta Zajuna del usuario autenticado."""
    user_id = request.state.user["id"]
    return _status_response(user_id)


@router.post("", response_model=AccountStatusResponse)
async def connect_account(
    body: ConnectAccountRequest,
    request: Request,
    config: ZajunaConfig = Depends(get_base_config),
) -> AccountStatusResponse:
    """Valida las credenciales EN VIVO contra Zajuna y las guarda cifradas.

    Nota: la validación hace el flujo de login real (3 pasos + delays
    humanos), tarda 10-30s — corre en el pool dedicado de Zajuna para no
    ocupar los hilos de la API.
    """
    user_id = request.state.user["id"]

    trial_config = config.model_copy(
        update={
            "zajuna_type_document": body.type_document,
            "zajuna_document": body.document,
            "zajuna_password": body.password,
        }
    )

    try:
        await run_in_zajuna_pool(AuthManager(trial_config).login)
    except ZajunaUnavailableError as exc:
        # Zajuna caída/inestable — NO son credenciales malas
        logger.warning("Zajuna no disponible al validar cuenta: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Zajuna no está respondiendo en este momento. Intenta de nuevo en unos minutos.",
        ) from exc
    except AuthError as exc:
        logger.warning(
            "Validación Zajuna fallida para usuario CMM %s (doc %s****): %s",
            user_id, body.document[:4], exc,
        )
        raise HTTPException(
            status_code=400,
            detail="Zajuna rechazó las credenciales. Verifica tu documento y contraseña.",
        ) from exc
    except Exception as exc:  # HTML inesperado u otro fallo no previsto
        logger.error("Error validando contra Zajuna: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="No fue posible validar contra Zajuna en este momento. Intenta de nuevo.",
        ) from exc

    vault.save_account(user_id, body.type_document, body.document, body.password)
    return _status_response(user_id)


@router.delete("", response_model=AccountStatusResponse)
def disconnect_account(request: Request) -> AccountStatusResponse:
    """Elimina las credenciales Zajuna del usuario autenticado."""
    user_id = request.state.user["id"]
    vault.delete_account(user_id)
    return AccountStatusResponse(connected=False)
