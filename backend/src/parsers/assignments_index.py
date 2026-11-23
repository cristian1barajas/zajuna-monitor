"""Parser for Zajuna Moodle Assignments Index page.

Parses /zajuna/mod/assign/index.php?id={course_id} to extract
assignment names and their course module IDs (cmids).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from src.parsers.grader import ParseError

logger = logging.getLogger(__name__)

# Regex to extract cmid from assignment links: /mod/assign/view.php?id=1343194
CMID_PATTERN = re.compile(r"/mod/assign/view\.php\?id=(\d+)")


@dataclass
class AssignmentEntry:
    """A single assignment from the assignments index page."""

    name: str  # Assignment name (e.g., "GA1-220501092-AA1-EV01 Infografia...")
    cmid: int  # Course module ID (from the URL)


def parse_assignments_index(html: str) -> list[AssignmentEntry]:
    """Parse the assignments index page and extract name + cmid for each assignment.

    Args:
        html: Raw HTML from /mod/assign/index.php?id={course_id}

    Returns:
        List of AssignmentEntry with name and cmid.

    Raises:
        ParseError: If the page structure is unexpected.
    """
    soup = BeautifulSoup(html, "lxml")

    # Find all links to assignment view pages
    links = soup.find_all("a", href=CMID_PATTERN)

    if not links:
        raise ParseError(
            "No assignment links found in assignments index page. "
            "The page may have a different structure or the course has no assignments."
        )

    assignments: list[AssignmentEntry] = []
    seen_cmids: set[int] = set()

    for link in links:
        href = link.get("href", "")
        match = CMID_PATTERN.search(href)
        if not match:
            continue

        cmid = int(match.group(1))
        if cmid in seen_cmids:
            continue
        seen_cmids.add(cmid)

        name = link.get_text(strip=True)
        if not name:
            logger.warning("Empty assignment name for cmid %d, skipping", cmid)
            continue

        assignments.append(AssignmentEntry(name=name, cmid=cmid))

    logger.info("Parsed %d assignments from index page", len(assignments))
    return assignments


def match_assignments_to_evidences(
    assignments: list[AssignmentEntry],
    evidences: list,
) -> list[dict]:
    """Match assignments (by name) to evidence items (by name) to build item_id -> cmid mapping.

    Uses normalized substring matching: if the assignment name contains the evidence name
    or vice versa (after normalization), they match.

    Args:
        assignments: Parsed assignments from the index page.
        evidences: Evidence objects from the grader report (with item_id and name attrs).

    Returns:
        List of dicts with name, cmid, and resolved item_id (or None).
    """
    result: list[dict] = []
    matched_count = 0

    # Build normalized evidence lookup
    evidence_lookup: list[tuple[str, int, str]] = []
    for ev in evidences:
        normalized = _normalize_name(ev.name)
        evidence_lookup.append((normalized, ev.item_id, ev.name))

    for assignment in assignments:
        norm_assign = _normalize_name(assignment.name)
        item_id = None

        # Try to find a matching evidence
        for norm_ev, ev_id, _ev_name in evidence_lookup:
            if _names_match(norm_assign, norm_ev):
                item_id = ev_id
                matched_count += 1
                break

        result.append({
            "name": assignment.name,
            "cmid": assignment.cmid,
            "item_id": item_id,
        })

    logger.info(
        "Matched %d/%d assignments to evidence items",
        matched_count, len(assignments),
    )
    return result


_GA_CODE_PATTERN = re.compile(r"GA\d+-\d+-AA\d+-EV\d+", re.IGNORECASE)


def _extract_ga_code(name: str) -> str | None:
    """Extract GA code (e.g., GA7-220501096-AA5-EV03) from a name."""
    match = _GA_CODE_PATTERN.search(name)
    return match.group(0).upper() if match else None


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, collapse whitespace."""
    return " ".join(name.lower().split())


def _names_match(name_a: str, name_b: str) -> bool:
    """Check if two normalized names match.

    Priority:
    1. If both names have GA codes, they must match exactly.
    2. Otherwise, matches if one contains the other or they share
       a significant common prefix (at least 30 chars).
    """
    if name_a == name_b:
        return True

    # If both have GA codes, use them for precise matching
    ga_a = _extract_ga_code(name_a)
    ga_b = _extract_ga_code(name_b)
    if ga_a and ga_b:
        return ga_a == ga_b

    if name_a in name_b or name_b in name_a:
        return True

    # Common prefix match (for cases where names are truncated)
    min_len = min(len(name_a), len(name_b))
    if min_len >= 30:
        prefix_len = 0
        for a, b in zip(name_a, name_b, strict=False):
            if a != b:
                break
            prefix_len += 1
        if prefix_len >= 30:
            return True

    return False
