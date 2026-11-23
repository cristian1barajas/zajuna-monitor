"""Parser de las publicaciones de una discusión de foro.

Lee /zajuna/mod/forum/discuss.php?d={discussion_id} en modo anidado (el que
Zajuna muestra por defecto). Cada publicación es un
``<article data-region="post" data-post-id="...">`` y sus respuestas van
dentro de su ``<div data-region="replies-container">``: el padre de una
publicación es el ``article`` más cercano que la contiene.

Por publicación se extrae: id, padre, asunto, autor (nombre y id de
usuario de Zajuna), fecha, texto limpio y el formulario de calificación si
el foro califica. No se guarda el ``sesskey`` del formulario.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

USER_ID_PATTERN = re.compile(r"user/view\.php\?id=(\d+)")
_POST_SELECTOR = {"data-region": "post"}


@dataclass
class PostRating:
    """Calificación de una publicación (formulario ``postratingform``)."""

    item_id: int | None
    scale_id: int | None
    context_id: int | None
    # Nota actual tal como la muestra Zajuna ("100", "A"…); None = sin calificar
    aggregate: str | None
    # (valor, etiqueta) de la escala, sin la opción "Calificar..." (-999)
    options: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ForumPost:
    post_id: int
    discussion_id: int
    parent_id: int | None
    subject: str
    author_name: str
    author_user_id: int | None
    created_at: datetime | None
    text: str
    rating: PostRating | None


def _clean(text: str) -> str:
    return " ".join(text.split())


def _parse_time(header: Tag | None) -> datetime | None:
    if header is None:
        return None
    time_tag = header.find("time")
    if time_tag is None:
        return None
    raw = (time_tag.get("datetime") or "").strip()
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            logger.debug("Fecha de publicación no reconocida: %r", raw)
    stamp = (time_tag.get("data-timestamp") or "").strip()
    if stamp.isdigit():
        return datetime.fromtimestamp(int(stamp), tz=UTC)
    return None


def _int_input(form: Tag, name: str) -> int | None:
    tag = form.find("input", attrs={"name": name})
    value = (tag.get("value") or "").strip() if tag else ""
    return int(value) if value.lstrip("-").isdigit() else None


def _parse_rating(article: Tag) -> PostRating | None:
    form = next(
        (f for f in article.find_all("form", class_="postratingform")
         if f.find_parent("article", attrs=_POST_SELECTOR) is article),
        None,
    )
    if form is None:
        return None
    aggregate_tag = form.find("span", class_="ratingaggregate")
    aggregate = _clean(aggregate_tag.get_text()) if aggregate_tag else ""
    options = [
        (str(o.get("value")), _clean(o.get_text()))
        for o in form.select("select[name=rating] option")
        if o.get("value") not in (None, "-999")
    ]
    return PostRating(
        item_id=_int_input(form, "itemid"),
        scale_id=_int_input(form, "scaleid"),
        context_id=_int_input(form, "contextid"),
        aggregate=aggregate if aggregate not in ("", "-") else None,
        options=options,
    )


def _own(article: Tag, tag: Tag | None) -> Tag | None:
    """``tag`` solo si pertenece a esta publicación y no a una respuesta anidada."""
    if tag is None:
        return None
    return tag if tag.find_parent("article", attrs=_POST_SELECTOR) is article else None


def _parse_article(article: Tag, discussion_id: int) -> ForumPost | None:
    post_id_raw = article.get("data-post-id") or ""
    if not post_id_raw.isdigit():
        return None
    post_id = int(post_id_raw)

    parent = article.find_parent("article", attrs=_POST_SELECTOR)
    parent_id = int(parent["data-post-id"]) if parent and str(parent.get("data-post-id", "")).isdigit() else None

    header = _own(article, article.find("header"))
    subject_tag = header.find("h3") if header else None
    author_tag = header.find("a", href=USER_ID_PATTERN) if header else None
    user_match = USER_ID_PATTERN.search(author_tag["href"]) if author_tag else None
    content = _own(article, article.find(id=f"post-content-{post_id}")) or _own(
        article, article.find(class_="post-content-container")
    )

    return ForumPost(
        post_id=post_id,
        discussion_id=discussion_id,
        parent_id=parent_id,
        subject=_clean(subject_tag.get_text()) if subject_tag else "",
        author_name=_clean(author_tag.get_text()) if author_tag else "",
        author_user_id=int(user_match.group(1)) if user_match else None,
        created_at=_parse_time(header),
        text=_clean(content.get_text(" ")) if content else "",
        rating=_parse_rating(article),
    )


def parse_forum_posts(html: str, discussion_id: int) -> list[ForumPost]:
    """Publicaciones de la discusión en el orden de la página (padre antes que hijos)."""
    soup = BeautifulSoup(html, "lxml")
    posts: list[ForumPost] = []
    seen: set[int] = set()
    for article in soup.find_all("article", attrs=_POST_SELECTOR):
        post = _parse_article(article, discussion_id)
        if post is None or post.post_id in seen:
            continue
        seen.add(post.post_id)
        posts.append(post)
    logger.debug("Discusión %d: %d publicaciones", discussion_id, len(posts))
    return posts
