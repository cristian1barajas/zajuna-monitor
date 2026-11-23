"""Bandeja de réplicas de un foro: qué aportes de aprendices esperan respuesta.

Reglas (ítem 9.1.6 de SAVA: responder los foros en máximo 1 día hábil):

- Autor: aprendiz si su id de Zajuna está entre los aprendices del grupo
  (snapshot); cualquier otro autor cuenta como instructor.
- Aporte: publicación de un aprendiz que abre la discusión o que responde a
  una publicación de un instructor. Las respuestas entre compañeros no son
  aportes: no esperan réplica del instructor.
- Respondido: hay una publicación de un instructor dentro del hilo del
  aporte (cualquier nivel de anidación).
- Plazo: el día hábil siguiente a la fecha del aporte (hora de Colombia).

El estado se recalcula con la fecha del día al leer: un aporte guardado
"a tiempo" ayer puede estar "vencido" hoy.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from src.parsers.forum_posts import ForumPost
from src.utils.business_days import business_days_between, local_date, next_business_day

EXCERPT_CHARS = 400

STATUS_OVERDUE = "vencido"
STATUS_DUE_TODAY = "vence_hoy"
STATUS_ON_TIME = "a_tiempo"
STATUS_REPLIED = "respondido"
STATUS_REPLIED_LATE = "respondido_tarde"


def apprentice_ids(snapshot: dict, ficha: str) -> set[int]:
    """Ids de Zajuna de los aprendices del grupo (calificador + participantes)."""
    ids: set[int] = set()
    for course in snapshot.get("courses", []):
        if course.get("ficha") == ficha:
            ids |= {int(s["user_id"]) for s in course.get("students", []) if s.get("user_id") is not None}
    for entry in snapshot.get("participants", []):
        if entry.get("ficha") == ficha:
            ids |= {int(p["user_id"]) for p in entry.get("participants", []) if p.get("user_id") is not None}
    return ids


def _excerpt(text: str) -> str:
    if len(text) <= EXCERPT_CHARS:
        return text
    return text[:EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"


def build_contributions(
    posts: Iterable[ForumPost],
    apprentices: set[int],
    discussion_title: str,
) -> tuple[list[dict], int]:
    """Aportes de una discusión (sin estado) y cuántas respuestas entre compañeros hubo.

    Cada aporte es un dict serializable que se guarda tal cual en el store.
    """
    posts = list(posts)
    by_id = {p.post_id: p for p in posts}
    children: dict[int, list[ForumPost]] = {}
    for p in posts:
        if p.parent_id is not None:
            children.setdefault(p.parent_id, []).append(p)

    def is_apprentice(p: ForumPost) -> bool:
        return p.author_user_id is not None and p.author_user_id in apprentices

    def first_instructor_reply(root: ForumPost) -> datetime | None:
        found: list[datetime] = []
        stack = list(children.get(root.post_id, []))
        while stack:
            node = stack.pop()
            if not is_apprentice(node) and node.created_at is not None:
                found.append(node.created_at)
            stack.extend(children.get(node.post_id, []))
        return min(found) if found else None

    contributions: list[dict] = []
    peer_replies = 0
    for p in posts:
        if not is_apprentice(p):
            continue
        parent = by_id.get(p.parent_id) if p.parent_id is not None else None
        if parent is not None and is_apprentice(parent):
            peer_replies += 1
            continue
        reply_at = first_instructor_reply(p)
        rating = p.rating
        contributions.append({
            "post_id": p.post_id,
            "discussion_id": p.discussion_id,
            "discussion_title": discussion_title,
            "parent_id": p.parent_id,
            "author_name": p.author_name,
            "author_user_id": p.author_user_id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "excerpt": _excerpt(p.text),
            "first_reply_at": reply_at.isoformat() if reply_at else None,
            "gradable": rating is not None,
            "grade": rating.aggregate if rating else None,
        })
    return contributions, peer_replies


def contribution_status(item: dict, today: date) -> dict:
    """Plazo, estado y días hábiles de espera de un aporte, a la fecha ``today``."""
    created = item.get("created_at")
    if not created:
        return {"reply_due": None, "status": STATUS_ON_TIME, "business_days_waiting": 0}
    created_day = local_date(datetime.fromisoformat(created))
    due = next_business_day(created_day)
    reply = item.get("first_reply_at")
    if reply:
        reply_day = local_date(datetime.fromisoformat(reply))
        status = STATUS_REPLIED if reply_day <= due else STATUS_REPLIED_LATE
        waiting = 0
    else:
        status = STATUS_OVERDUE if today > due else STATUS_DUE_TODAY if today == due else STATUS_ON_TIME
        waiting = business_days_between(created_day, today)
    return {"reply_due": due.isoformat(), "status": status, "business_days_waiting": waiting}


def count_overdue(contributions: Iterable[dict], today: date, since: date | None = None) -> int:
    """Aportes vencidos a la fecha; con ``since``, solo los publicados desde ese día."""
    total = 0
    for c in contributions:
        if since is not None and (
            not c.get("created_at") or local_date(datetime.fromisoformat(c["created_at"])) < since
        ):
            continue
        if contribution_status(c, today)["status"] == STATUS_OVERDUE:
            total += 1
    return total
