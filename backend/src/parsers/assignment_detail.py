"""Parser for individual Zajuna Moodle Assignment page.

Parses /zajuna/mod/assign/view.php?id={cmid} to extract
grading summary info (participants, submitted, needs_grading, etc.).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class AssignmentGradingInfo:
    """Grading summary extracted from an individual assignment page."""

    cmid: int
    participants: int = 0
    drafts: int = 0
    submitted: int = 0
    needs_grading: int = 0  # "Pendientes por calificar"
    time_remaining: str | None = None


# Labels in the summary table (Spanish, as shown in Zajuna)
_LABEL_MAP = {
    "participantes": "participants",
    "borradores": "drafts",
    "enviados": "submitted",
    "pendientes por calificar": "needs_grading",
    "tiempo restante": "time_remaining",
}


def parse_assignment_detail(html: str, cmid: int) -> AssignmentGradingInfo:
    """Parse an individual assignment page and extract grading summary.

    Args:
        html: Raw HTML from /mod/assign/view.php?id={cmid}
        cmid: The course module ID for this assignment.

    Returns:
        AssignmentGradingInfo with parsed data (zeros if summary not found).
    """
    soup = BeautifulSoup(html, "lxml")
    info = AssignmentGradingInfo(cmid=cmid)

    # Strategy 1: Look for the summary table in the grading summary section
    # Moodle typically wraps it in a <div class="submissionlinks"> or a table
    tables = soup.find_all("table", class_="generaltable")

    found = False
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)

                field = _LABEL_MAP.get(label)
                if field:
                    found = True
                    if field == "time_remaining":
                        info.time_remaining = value
                    else:
                        try:
                            setattr(info, field, int(value))
                        except ValueError:
                            logger.warning(
                                "Non-integer value '%s' for field '%s' in cmid %d",
                                value, field, cmid,
                            )

    # Strategy 2: If no table found, try looking for the summary in other formats
    if not found:
        # Try finding text content with the key labels
        text = soup.get_text()
        for label, field in _LABEL_MAP.items():
            pattern = re.compile(
                rf"{re.escape(label)}\s*[:\-]?\s*(\d+)", re.IGNORECASE
            )
            match = pattern.search(text)
            if match:
                found = True
                if field != "time_remaining":
                    setattr(info, field, int(match.group(1)))

    if not found:
        logger.warning(
            "No grading summary found for cmid %d. "
            "The assignment may be offline or have a non-standard layout. "
            "Returning zeros.",
            cmid,
        )

    logger.info(
        "Parsed assignment cmid=%d: participants=%d, submitted=%d, needs_grading=%d",
        cmid, info.participants, info.submitted, info.needs_grading,
    )
    return info
