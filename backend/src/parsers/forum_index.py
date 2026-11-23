"""Parser for Zajuna Moodle Forum Index page.

Parses /zajuna/mod/forum/index.php?id={course_id} to extract
forum names and their forum instance IDs.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from src.parsers.assignments_index import _names_match, _normalize_name
from src.parsers.grader import ParseError

logger = logging.getLogger(__name__)

# Regex to extract forum_id from links: view.php?f=565694
FORUM_ID_PATTERN = re.compile(r"view\.php\?f=(\d+)")


@dataclass
class ForumEntry:
    """A single forum from the forum index page."""

    name: str       # Forum name (e.g., "Foro temático - Fuentes de requisitos...")
    forum_id: int   # Forum instance ID (from the f= URL parameter)


def parse_forum_index(html: str) -> list[ForumEntry]:
    """Parse the forum index page and extract name + forum_id for each forum.

    Args:
        html: Raw HTML from /mod/forum/index.php?id={course_id}

    Returns:
        List of ForumEntry with name and forum_id.

    Raises:
        ParseError: If no forum links are found.
    """
    soup = BeautifulSoup(html, "lxml")

    links = soup.find_all("a", href=FORUM_ID_PATTERN)

    if not links:
        raise ParseError(
            "No forum links found in forum index page. "
            "The course may have no forums."
        )

    forums: list[ForumEntry] = []
    seen_ids: set[int] = set()

    for link in links:
        href = link.get("href", "")
        match = FORUM_ID_PATTERN.search(href)
        if not match:
            continue

        forum_id = int(match.group(1))
        if forum_id in seen_ids:
            continue
        seen_ids.add(forum_id)

        name = link.get_text(strip=True)
        if not name:
            continue

        # Skip numeric-only text (these are discussion count links)
        if name.isdigit():
            continue

        forums.append(ForumEntry(name=name, forum_id=forum_id))

    logger.info("Parsed %d forums from index page", len(forums))
    return forums


def match_forums_to_evidences(
    forums: list[ForumEntry],
    evidences: list,
) -> list[dict]:
    """Match forums (by name) to evidence items to build item_id -> forum_id mapping.

    Uses normalized substring matching, same logic as assignments matching.

    Args:
        forums: Parsed forums from the index page.
        evidences: Evidence objects from grader report (with item_id and name attrs).

    Returns:
        List of dicts with name, cmid (forum_id), item_id, and module_type.
    """
    result: list[dict] = []
    matched_count = 0

    evidence_lookup: list[tuple[str, int, str]] = []
    for ev in evidences:
        normalized = _normalize_name(ev.name)
        evidence_lookup.append((normalized, ev.item_id, ev.name))

    for forum in forums:
        norm_forum = _normalize_name(forum.name)
        item_id = None

        for norm_ev, ev_id, _ev_name in evidence_lookup:
            if _names_match(norm_forum, norm_ev):
                item_id = ev_id
                matched_count += 1
                break

        result.append({
            "name": forum.name,
            "cmid": forum.forum_id,
            "item_id": item_id,
            "module_type": "forum",
        })

    logger.info(
        "Matched %d/%d forums to evidence items",
        matched_count, len(forums),
    )
    return result
