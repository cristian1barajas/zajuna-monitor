"""Foros: aportes de aprendices que esperan réplica del instructor (SAVA 9.1.6).

Fase 1, solo lectura: nada se publica en Zajuna.

- ``GET  /api/fichas/{ficha}/foros``: foros del grupo con el resumen de su
  última revisión (sin entrar a Zajuna).
- ``POST /api/fichas/{ficha}/foros/{forum_id}/revisar``: lee en Zajuna todas
  las discusiones del foro, guarda el resultado y lo devuelve.
- ``GET  /api/fichas/{ficha}/foros/{forum_id}/participaciones``: la última
  revisión guardada, con el estado recalculado a la fecha de hoy.

El guard global ``require_ficha_access`` ya valida la ficha; además el
``forum_id`` debe ser un foro del mapeo de la ficha, así no se consulta en
Zajuna un id arbitrario.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException

from src.api import response_cache
from src.api.dependencies import get_base_config, get_config, get_snapshot
from src.api.forum_inbox import (
    STATUS_DUE_TODAY,
    STATUS_ON_TIME,
    STATUS_OVERDUE,
    STATUS_REPLIED,
    STATUS_REPLIED_LATE,
    apprentice_ids,
    build_contributions,
    contribution_status,
)
from src.api.routes.pending_grading import _account_lock, _shared_client
from src.api.schemas import (
    ForumContribution,
    ForumCounts,
    ForumInboxResponse,
    ForumListResponse,
    ForumSummaryItem,
)
from src.client.zajuna import FetchError, ZajunaClient
from src.config import ZajunaConfig
from src.parsers.forum_detail import parse_forum_discussions
from src.parsers.forum_posts import parse_forum_posts
from src.parsers.grader import ParseError
from src.store.assignments_store import load_assignments
from src.store.forum_replies_store import load_forum, load_forum_replies, save_forum
from src.utils.business_days import today_colombia

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fichas", tags=["forums"])

_STATUS_COUNTER = {
    STATUS_OVERDUE: "overdue",
    STATUS_DUE_TODAY: "due_today",
    STATUS_ON_TIME: "on_time",
    STATUS_REPLIED: "replied",
    STATUS_REPLIED_LATE: "replied_late",
}


def _forums_of(ficha: str) -> list[dict]:
    data = load_assignments(ficha)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay mapeo de evidencias para el grupo {ficha}. Sincroniza primero.",
        )
    return [a for a in data["assignments"] if a.get("module_type") == "forum"]


def _forum_or_404(ficha: str, forum_id: int) -> dict:
    forum = next((f for f in _forums_of(ficha) if f["cmid"] == forum_id), None)
    if forum is None:
        raise HTTPException(status_code=404, detail="Ese foro no está en el grupo.")
    return forum


def _discussion_url(base_url: str, discussion_id: int, post_id: int) -> str:
    return f"{base_url}/zajuna/mod/forum/discuss.php?d={discussion_id}#p{post_id}"


def _counts(items: list[ForumContribution]) -> ForumCounts:
    counts = ForumCounts(contributions=len(items))
    for item in items:
        field = _STATUS_COUNTER.get(item.status)
        if field:
            setattr(counts, field, getattr(counts, field) + 1)
        if item.gradable and item.grade is None:
            counts.ungraded += 1
    return counts


def _with_status(stored: list[dict], today: date, base_url: str) -> list[ForumContribution]:
    items = [
        ForumContribution(
            **c,
            **contribution_status(c, today),
            url=_discussion_url(base_url, c["discussion_id"], c["post_id"]),
        )
        for c in stored
    ]
    # Lo más antiguo primero: es lo que lleva más tiempo esperando
    items.sort(key=lambda c: c.created_at or "")
    return items


def _response(ficha: str, forum: dict, today: date, base_url: str) -> ForumInboxResponse:
    items = _with_status(forum.get("contributions", []), today, base_url)
    return ForumInboxResponse(
        ficha=ficha,
        forum_id=forum["forum_id"],
        item_id=forum.get("item_id"),
        name=forum["name"],
        checked_at=forum["checked_at"],
        total_discussions=forum.get("total_discussions", 0),
        peer_replies=forum.get("peer_replies", 0),
        failed_discussions=forum.get("failed_discussions", []),
        counts=_counts(items),
        contributions=items,
    )


def _scrape_forum(client: ZajunaClient, forum: dict, apprentices: set[int]) -> dict:
    """Lee el foro completo. Los hilos que fallen se reintentan una vez."""
    forum_id = forum["cmid"]
    try:
        view_html = client.fetch_forum_view(forum_id)
        discussions = parse_forum_discussions(view_html, forum_id)
    except ParseError:
        discussions = []  # foro sin discusiones todavía
    except FetchError as e:
        raise HTTPException(status_code=502, detail=f"Zajuna no respondió al abrir el foro: {e}") from e

    contributions: list[dict] = []
    peer_replies = 0
    pending = list(discussions)
    for _round in range(2):
        failed = []
        for disc in pending:
            try:
                html = client.fetch_forum_discussion(disc.discussion_id)
                posts = parse_forum_posts(html, disc.discussion_id)
            except (FetchError, ParseError) as e:
                logger.warning("Discusión %d no se pudo leer: %s", disc.discussion_id, e)
                failed.append(disc)
                continue
            found, peers = build_contributions(posts, apprentices, disc.title)
            contributions.extend(found)
            peer_replies += peers
        pending = failed
        if not pending:
            break

    return {
        "forum_id": forum_id,
        "item_id": forum.get("item_id"),
        "name": forum["name"],
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "total_discussions": len(discussions),
        "peer_replies": peer_replies,
        "failed_discussions": [d.discussion_id for d in pending],
        "contributions": contributions,
    }


@router.get("/{ficha}/foros", response_model=ForumListResponse)
def list_forums(ficha: str, config: ZajunaConfig = Depends(get_base_config)):
    today = today_colombia()
    stored = (load_forum_replies(ficha) or {}).get("forums", {})
    forums = []
    for f in _forums_of(ficha):
        saved = stored.get(str(f["cmid"]))
        counts = None
        if saved:
            counts = _counts(_with_status(saved.get("contributions", []), today, config.zajuna_base_url))
        forums.append(ForumSummaryItem(
            forum_id=f["cmid"],
            item_id=f.get("item_id"),
            name=f["name"],
            graded=f.get("item_id") is not None,
            checked_at=saved["checked_at"] if saved else None,
            counts=counts,
        ))
    return ForumListResponse(ficha=ficha, today=today.isoformat(), forums=forums)


@router.get("/{ficha}/foros/{forum_id}/participaciones", response_model=ForumInboxResponse)
def get_forum_inbox(ficha: str, forum_id: int, config: ZajunaConfig = Depends(get_base_config)):
    _forum_or_404(ficha, forum_id)
    saved = load_forum(ficha, forum_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Este foro todavía no se ha revisado.")
    return _response(ficha, saved, today_colombia(), config.zajuna_base_url)


@router.post("/{ficha}/foros/{forum_id}/revisar", response_model=ForumInboxResponse)
def check_forum(
    ficha: str,
    forum_id: int,
    config: ZajunaConfig = Depends(get_config),
    snapshot: dict = Depends(get_snapshot),
):
    forum = _forum_or_404(ficha, forum_id)
    apprentices = apprentice_ids(snapshot, ficha)
    if not apprentices:
        raise HTTPException(
            status_code=409,
            detail="No hay aprendices del grupo en la última sincronización. Sincroniza primero.",
        )
    with _account_lock(config):
        client = _shared_client(config)
        result = _scrape_forum(client, forum, apprentices)
    save_forum(ficha, result)
    # Las alertas leen esta revisión: que no se sirvan desde el cache
    response_cache.clear()
    return _response(ficha, result, today_colombia(), config.zajuna_base_url)
