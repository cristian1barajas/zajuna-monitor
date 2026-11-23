"""Parser for the Zajuna Moodle Participants page HTML."""
from __future__ import annotations

import logging
import re
import unicodedata

from bs4 import BeautifulSoup, Tag

from src.models.schemas import (
    CourseParticipants,
    Participant,
    StudentStatus,
)
from src.parsers.grader import DOCUMENT_SUFFIX_PATTERN, FICHA_PATTERN, ParseError

logger = logging.getLogger(__name__)

# Regex to extract user_id from profile link: /user/view.php?id=2254444&course=89977
USER_ID_PATTERN = re.compile(r"[?&]id=(\d+)")

# Regex to capture (number, unit) pairs from Spanish relative time strings
# Examples: "12 días 17 horas", "1 año 171 días", "333 días 7 horas"
TIME_PAIR_PATTERN = re.compile(r"(\d+)\s+(\w+)")

# Unit multipliers in days
TIME_UNITS: dict[str, float] = {
    "segundo": 0,
    "segundos": 0,
    "minuto": 0,
    "minutos": 0,
    "hora": 0,
    "horas": 0,
    "dia": 1,
    "dias": 1,
    "mes": 30,
    "meses": 30,
    "ano": 365,
    "anos": 365,
}


def _normalize_text(text: str) -> str:
    """Remove diacritics (accents) from text for unit matching.

    "días" -> "dias", "año" -> "ano"
    """
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def parse_last_access_to_days(raw: str) -> int:
    """Convert a Spanish relative time string to integer days.

    Examples:
        "8 segundos"        -> 0
        "13 horas 58 minutos" -> 0
        "12 días 17 horas"  -> 12
        "47 días"           -> 47
        "333 días 7 horas"  -> 333
        "1 año 171 días"    -> 536  (365 + 171)
        "Nunca"             -> 9999
        "ahora"             -> 0
        ""                  -> -1
    """
    raw = raw.strip()
    if not raw:
        return -1

    normalized = _normalize_text(raw.lower())

    if normalized == "nunca":
        return 9999
    if normalized == "ahora":
        return 0

    pairs = TIME_PAIR_PATTERN.findall(normalized)
    if not pairs:
        logger.warning("Could not parse last access: %r", raw)
        return -1

    total_days = 0
    for number_str, unit in pairs:
        multiplier = TIME_UNITS.get(unit, 0)
        total_days += int(number_str) * multiplier

    return total_days


class ParticipantsParser:
    """Parses a Zajuna course participants page into structured data.

    HTML structure:
    - Table: <table id="participants">
    - Rows: <tr id="user-index-participants-{course_id}_r{N}">
    - c0 (td): Checkbox with input id="user{USER_ID}" + label with name
    - c1 (th): Name link with <span class="userinitials"> prefix
    - c2 (td): Username/cédula with document type suffix (cc, TI)
    - c3 (td): Email
    - c4 (td): Role ("Aprendiz", "Instructor", etc.)
    - c5 (td): Groups
    - c6 (td): Last access ("12 días 17 horas", "Nunca", "ahora")
    - c7 (td): Status div with data-status attribute and badge span
    """

    def __init__(self, html: str, course_id: int) -> None:
        self.soup = BeautifulSoup(html, "lxml")
        self.course_id = course_id
        self._table: Tag | None = None

    def parse(self) -> CourseParticipants:
        """Execute the full parsing pipeline. Returns a CourseParticipants."""
        self._table = self.soup.find("table", id="participants")
        if not self._table:
            raise ParseError(
                f"Table #participants not found for course {self.course_id}"
            )

        course_name = self._extract_course_name()
        ficha = self._extract_ficha(course_name)
        participants = self._extract_participants()

        result = CourseParticipants(
            course_id=self.course_id,
            ficha=ficha,
            participants=participants,
        )

        logger.info(
            "Parsed course %d (ficha %s): %d participants (Aprendiz only)",
            self.course_id, ficha, len(participants),
        )
        return result

    def _extract_course_name(self) -> str:
        """Extract course name from <title> tag.

        Expected: "P_228118_V_3388997_R_11_C_9214: Participantes | Zajuna"
        """
        title_tag = self.soup.find("title")
        if not title_tag:
            raise ParseError("No <title> tag found")
        return title_tag.get_text(strip=True)

    def _extract_ficha(self, course_name: str) -> str:
        """Extract ficha number from course/page name."""
        match = FICHA_PATTERN.search(course_name)
        if match:
            return match.group(1)

        # Try from data-coursename in status cells
        status_div = self._table.find("div", attrs={"data-coursename": True})
        if status_div:
            coursename = status_div["data-coursename"]
            match = FICHA_PATTERN.search(coursename)
            if match:
                return match.group(1)

        logger.warning(
            "Could not extract ficha from course name: %s", course_name
        )
        return ""

    def _extract_participants(self) -> list[Participant]:
        """Extract all Aprendiz participants from the table."""
        participants: list[Participant] = []

        rows = self._table.find_all("tr", id=True)
        for tr in rows:
            participant = self._parse_participant_row(tr)
            if participant and participant.role == "Aprendiz":
                participants.append(participant)

        logger.debug("Extracted %d Aprendiz participants", len(participants))
        return participants

    def _parse_participant_row(self, tr: Tag) -> Participant | None:
        """Parse one <tr> into a Participant.

        Returns None for empty rows (rows with no name/role).
        """
        # Get all td cells
        cells = tr.find_all("td")
        if len(cells) < 7:
            return None

        # The name cell is a <th>, not <td>
        name_th = tr.find("th", class_="cell")

        # Skip empty rows (ghost rows from perpage)
        role = cells[3].get_text(strip=True)  # c4 is the 4th td (index 3)
        if not role:
            return None

        # User ID: from checkbox input or profile link
        user_id = self._extract_user_id(cells[0], name_th)
        if user_id is None:
            return None

        # Full name: from <th> name link
        full_name = self._extract_full_name(name_th)

        # Document (cédula): clean suffix from username cell
        raw_username = cells[1].get_text(strip=True)  # c2
        document = DOCUMENT_SUFFIX_PATTERN.sub("", raw_username)

        # Email
        email = cells[2].get_text(strip=True)  # c3

        # Groups
        groups = cells[4].get_text(strip=True)  # c5

        # Last access
        last_access_raw = cells[5].get_text(strip=True)  # c6
        last_access_days = parse_last_access_to_days(last_access_raw)

        # Status: from data-status attribute or badge text
        status = self._extract_status(cells[6])  # c7

        return Participant(
            user_id=user_id,
            full_name=full_name,
            document=document,
            email=email,
            role=role,
            groups=groups,
            last_access_raw=last_access_raw,
            last_access_days=last_access_days,
            status=status,
        )

    def _extract_user_id(
        self, checkbox_cell: Tag, name_th: Tag | None
    ) -> int | None:
        """Extract user_id from checkbox input or profile link."""
        # Try checkbox input: id="user2254444"
        inp = checkbox_cell.find("input", class_="usercheckbox")
        if inp:
            inp_id = inp.get("id", "")
            if inp_id.startswith("user"):
                try:
                    return int(inp_id[4:])
                except ValueError:
                    pass

        # Fallback: profile link in name cell
        if name_th:
            link = name_th.find("a", href=True)
            if link:
                match = USER_ID_PATTERN.search(link["href"])
                if match:
                    return int(match.group(1))

        return None

    def _extract_full_name(self, name_th: Tag | None) -> str:
        """Extract clean full name from the name <th> cell."""
        if not name_th:
            return ""

        link = name_th.find("a")
        if not link:
            return name_th.get_text(strip=True)

        # Remove userinitials span before extracting text
        initials_span = link.find("span", class_="userinitials")
        if initials_span:
            initials_span.decompose()

        return " ".join(link.get_text(strip=True).split())

    def _extract_status(self, status_cell: Tag) -> StudentStatus:
        """Extract enrollment status from the status cell."""
        # Try data-status attribute on the div
        status_div = status_cell.find("div", attrs={"data-status": True})
        if status_div:
            raw_status = status_div["data-status"]
            try:
                return StudentStatus(raw_status)
            except ValueError:
                logger.warning("Unknown status: %r", raw_status)

        # Fallback: badge text
        badge = status_cell.find("span", class_="badge")
        if badge:
            raw_status = badge.get_text(strip=True)
            try:
                return StudentStatus(raw_status)
            except ValueError:
                logger.warning("Unknown badge status: %r", raw_status)

        return StudentStatus.ACTIVE
