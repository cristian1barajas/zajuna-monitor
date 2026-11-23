"""Parser for Moodle assignment submissions (grading) page.

Parses the HTML from /mod/assign/view.php?id={cmid}&action=grading
to extract student submission data including file download URLs.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Regex to strip letter suffix from Moodle usernames (e.g., "1000000001cc" -> "1000000001")
_USERNAME_SUFFIX = re.compile(r"[a-zA-Z]{1,2}$")

# Regex to extract instrument URL from onclick attribute
_INSTRUMENT_ONCLICK = re.compile(r"window\.open\(['\"]([^'\"]+)['\"]")


@dataclass
class SubmissionEntry:
    """One student's submission data from the grading table."""

    user_id: int
    full_name: str
    document: str  # cédula (username without letter suffix)
    email: str
    status: str  # "Sin entrega", "Enviado para calificar", "Calificado", etc.
    is_graded: bool  # Whether the submission has been graded
    last_modified: str | None = None
    file_urls: list[str] = field(default_factory=list)
    file_names: list[str] = field(default_factory=list)


@dataclass
class SubmissionsPage:
    """Parsed data from the assignment submissions page."""

    cmid: int
    assignment_name: str
    entries: list[SubmissionEntry] = field(default_factory=list)
    instrument_url: str | None = None
    instrument_name: str | None = None

    @property
    def statuses(self) -> list[str]:
        """Unique submission statuses found."""
        seen: set[str] = set()
        result: list[str] = []
        for e in self.entries:
            if e.status not in seen:
                seen.add(e.status)
                result.append(e.status)
        return result


def parse_submissions_page(html: str, cmid: int) -> SubmissionsPage:
    """Parse the assignment grading page HTML.

    Args:
        html: Raw HTML from /mod/assign/view.php?id={cmid}&action=grading
        cmid: The course module ID.

    Returns:
        SubmissionsPage with parsed entries.
    """
    soup = BeautifulSoup(html, "lxml")

    # Extract assignment name from <h2>
    h2 = soup.find("h2")
    assignment_name = h2.get_text(strip=True) if h2 else f"Assignment {cmid}"

    # Extract instrument URL from onclick buttons
    instrument_url, instrument_name = _extract_instrument(soup)

    # Find the grading table
    table = soup.find("table", class_="generaltable")
    if not table:
        logger.warning("No grading table found for cmid %d", cmid)
        return SubmissionsPage(
            cmid=cmid,
            assignment_name=assignment_name,
            instrument_url=instrument_url,
            instrument_name=instrument_name,
        )

    entries: list[SubmissionEntry] = []

    # Student rows have an input[name="selectedusers"]
    for row in table.find_all("tr"):
        checkbox = row.find("input", attrs={"name": "selectedusers"})
        if not checkbox:
            continue

        user_id = int(checkbox.get("value", 0))

        # Name: cell with class c2 containing user link
        name_cell = row.find("td", class_="c2")
        name_link = name_cell.find("a") if name_cell else None
        full_name = name_link.get_text(strip=True) if name_link else ""

        # Username (cédula): cell with class "username"
        username_cell = row.find("td", class_="username")
        raw_username = username_cell.get_text(strip=True) if username_cell else ""
        document = _USERNAME_SUFFIX.sub("", raw_username)

        # Email: cell with class "email"
        email_cell = row.find("td", class_="email")
        email = email_cell.get_text(strip=True) if email_cell else ""

        # Status: first div in status cell (c5)
        status_cell = row.find("td", class_="c5")
        status, is_graded = _parse_status(status_cell)

        # Last modified: cell c8
        last_mod_cell = row.find("td", class_="c8")
        last_modified = None
        if last_mod_cell:
            text = last_mod_cell.get_text(strip=True)
            if text and text != "-":
                last_modified = text

        # File URLs: links containing "pluginfile" in file submission cell (c10)
        file_urls: list[str] = []
        file_names: list[str] = []
        # Look through all cells for pluginfile links (cell index may vary)
        for link in row.find_all("a", href=True):
            href = link["href"]
            if "pluginfile" in href and "submission_files" in href:
                file_urls.append(href)
                # Extract filename: text content without icon text
                img = link.find("img")
                if img:
                    img.extract()
                fname = link.get_text(strip=True)
                file_names.append(fname)

        entries.append(
            SubmissionEntry(
                user_id=user_id,
                full_name=full_name,
                document=document,
                email=email,
                status=status,
                is_graded=is_graded,
                last_modified=last_modified,
                file_urls=file_urls,
                file_names=file_names,
            )
        )

    logger.info(
        "Parsed submissions for cmid %d: %d entries, %d with files",
        cmid,
        len(entries),
        sum(1 for e in entries if e.file_urls),
    )

    return SubmissionsPage(
        cmid=cmid,
        assignment_name=assignment_name,
        entries=entries,
        instrument_url=instrument_url,
        instrument_name=instrument_name,
    )


def parse_instrument_url(html: str) -> tuple[str | None, str | None]:
    """Extract instrument URL from an assignment detail page (without action=grading).

    The instrument link is typically a button with onclick="window.open('...')".

    Returns:
        (url, name) tuple, or (None, None) if not found.
    """
    soup = BeautifulSoup(html, "lxml")
    return _extract_instrument(soup)


def _extract_instrument(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """Extract instrument of evaluation URL from page."""
    for button in soup.find_all("button"):
        text = button.get_text(strip=True).lower()
        if "instrumento" in text and "evaluaci" in text:
            onclick = button.get("onclick", "")
            match = _INSTRUMENT_ONCLICK.search(onclick)
            if match:
                url = match.group(1)
                # Derive name from URL
                name = url.rsplit("/", 1)[-1] if "/" in url else None
                return url, name
    return None, None


def _parse_status(status_cell) -> tuple[str, bool]:
    """Parse the status cell to extract primary status and grading state.

    Returns:
        (status_text, is_graded) tuple.
    """
    if not status_cell:
        return "Sin entrega", False

    is_graded = bool(status_cell.find("div", class_="submissiongraded"))

    # Primary status is the first div
    status_div = status_cell.find("div", class_=re.compile(r"submissionstatus"))
    if status_div:
        return status_div.get_text(strip=True), is_graded

    # Fallback: use full text
    text = status_cell.get_text(strip=True)
    return text or "Sin entrega", is_graded
