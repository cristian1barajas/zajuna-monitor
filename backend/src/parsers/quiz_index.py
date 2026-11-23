"""Parser for Zajuna Moodle Quiz Index page.

Parses /zajuna/mod/quiz/index.php?id={course_id} to extract
quiz names and their course module IDs (cmids).

Quizzes are auto-graded by Moodle, so they don't need manual grading.

HTML structure (from real Zajuna):
    <table class="generaltable">
      <tr>
        <td>Sección</td>
        <td><a href="view.php?id=5967188">Cuestionario. GA1-...</a></td>
        <td>Sin fecha de cierre</td>
        <td><a href=".../report.php?id=5967188&mode=overview">Intentos: 18</a></td>
      </tr>
    </table>

Note: Quiz links are RELATIVE (view.php?id=...), unlike navbar links which
are absolute (https://zajuna.sena.edu.co/zajuna/course/view.php?id=...).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from src.parsers.assignments_index import _names_match, _normalize_name
from src.parsers.grader import ParseError

logger = logging.getLogger(__name__)

# Relative quiz view link: "view.php?id=5967188" (NOT absolute URLs)
_RELATIVE_VIEW_PATTERN = re.compile(r"^view\.php\?id=(\d+)$")


@dataclass
class QuizEntry:
    """A single quiz from the quiz index page."""

    name: str  # Quiz name (e.g., "Cuestionario. GA1-240202501-AA1-EV01")
    cmid: int  # Course module ID (from the URL)


def parse_quiz_index(html: str) -> list[QuizEntry]:
    """Parse the quiz index page and extract name + cmid for each quiz.

    Args:
        html: Raw HTML from /mod/quiz/index.php?id={course_id}

    Returns:
        List of QuizEntry with name and cmid.

    Raises:
        ParseError: If no quiz links are found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Find the generaltable (quiz listing table)
    table = soup.find("table", class_="generaltable")
    if not table:
        raise ParseError(
            "No generaltable found in quiz index page. "
            "The page may have a different structure."
        )

    # Find relative view.php links inside the table only
    links = table.find_all("a", href=_RELATIVE_VIEW_PATTERN)

    if not links:
        raise ParseError(
            "No quiz links found in quiz index table. "
            "The course may have no quizzes."
        )

    quizzes: list[QuizEntry] = []
    seen_cmids: set[int] = set()

    for link in links:
        href = link.get("href", "")
        match = _RELATIVE_VIEW_PATTERN.search(href)
        if not match:
            continue

        cmid = int(match.group(1))
        if cmid in seen_cmids:
            continue
        seen_cmids.add(cmid)

        name = link.get_text(strip=True)
        if not name:
            logger.warning("Empty quiz name for cmid %d, skipping", cmid)
            continue

        quizzes.append(QuizEntry(name=name, cmid=cmid))

    logger.info("Parsed %d quizzes from index page", len(quizzes))
    return quizzes


def match_quizzes_to_evidences(
    quizzes: list[QuizEntry],
    evidences: list,
) -> list[dict]:
    """Match quizzes (by name) to evidence items to build item_id -> cmid mapping.

    Uses the same matching as assignments and forums: when both names carry
    a GA code it must match exactly, so AA1-EV01 and AA2-EV01 of the same
    guide never collide.

    Args:
        quizzes: Parsed quizzes from the index page.
        evidences: Evidence objects from grader report (with item_id and name attrs).

    Returns:
        List of dicts with name, cmid, item_id, and module_type="quiz".
    """
    result: list[dict] = []
    matched_count = 0

    evidence_lookup: list[tuple[str, int, str]] = []
    for ev in evidences:
        normalized = _normalize_name(ev.name)
        evidence_lookup.append((normalized, ev.item_id, ev.name))

    for quiz in quizzes:
        norm_quiz = _normalize_name(quiz.name)
        item_id = None

        for norm_ev, ev_id, _ev_name in evidence_lookup:
            if _names_match(norm_quiz, norm_ev):
                item_id = ev_id
                matched_count += 1
                break

        result.append({
            "name": quiz.name,
            "cmid": quiz.cmid,
            "item_id": item_id,
            "module_type": "quiz",
        })

    logger.info(
        "Matched %d/%d quizzes to evidence items",
        matched_count, len(quizzes),
    )
    return result
