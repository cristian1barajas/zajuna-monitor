"""Parser for the Zajuna Moodle Grader Report HTML."""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup, Tag

from src.models.schemas import (
    CourseReport,
    CourseSummary,
    Evidence,
    GradeCell,
    GradeStatus,
    StudentRow,
)

logger = logging.getLogger(__name__)

# Regex to extract ficha number from course name: "(3388997)"
FICHA_PATTERN = re.compile(r"\((\d{7})\)")

# Regex to extract item_id from CSS class: "i2506476"
ITEM_ID_PATTERN = re.compile(r"\bi(\d+)\b")

# Regex to strip document suffix (e.g., "cc", "CC", "ti", "TI")
DOCUMENT_SUFFIX_PATTERN = re.compile(r"[a-zA-Z]{1,2}$")


class ParseError(Exception):
    """Raised when HTML parsing fails."""


class GraderParser:
    """Parses a Zajuna Grader Report HTML into structured data.

    HTML structure overview (from real 15MB sample):
    - Table: <table id="user-grades" class="gradereport-grader-table d-none">
    - Header rows contain category headers (catlevel2) and evidence headers
    - Student rows: <tr class="userrow odd|even" data-uid="USER_ID">
    - Grade cells: <td class="gradecell grade iITEM_ID" data-itemid="ITEM_ID">
    - Values: <span class="gradevalue [gradepass]">A|D|-</span>

    Important: Must EXCLUDE "categoryitem" and "courseitem" from evidence parsing.
    Only columns with class "item catlevel2 highlightable" are real evidences.
    """

    def __init__(self, html: str, course_id: int) -> None:
        self.soup = BeautifulSoup(html, "lxml")
        self.course_id = course_id
        self._table: Tag | None = None

    def parse(self) -> CourseReport:
        """Execute the full parsing pipeline. Returns a CourseReport."""
        self._table = self.soup.find("table", id="user-grades")
        if not self._table:
            raise ParseError(
                f"Table #user-grades not found for course {self.course_id}"
            )

        course_name = self._extract_course_name()
        ficha = self._extract_ficha(course_name)
        evidences = self._extract_evidence_headers()
        evidence_ids = {e.item_id for e in evidences}
        students = self._extract_students(evidence_ids)

        report = CourseReport(
            course_id=self.course_id,
            course_name=course_name,
            ficha=ficha,
            evidences=evidences,
            students=students,
        )

        logger.info(
            "Parsed course %d (ficha %s): %d evidences, %d students",
            self.course_id, ficha, len(evidences), len(students),
        )
        return report

    def _extract_course_name(self) -> str:
        """Extract course name from <title> tag.

        Expected: "Informe del calificador | COURSE_NAME | Zajuna"
        """
        title_tag = self.soup.find("title")
        if not title_tag:
            raise ParseError("No <title> tag found")

        title_text = title_tag.get_text(strip=True)
        parts = title_text.split(" | ")
        if len(parts) >= 2:
            return parts[1].strip()
        return title_text

    def _extract_ficha(self, course_name: str) -> str:
        """Extract ficha number from course name.

        Example: "ANALISIS Y DESARROLLO DE SOFTWARE. (3388997)" -> "3388997"
        """
        match = FICHA_PATTERN.search(course_name)
        if match:
            return match.group(1)
        logger.warning(
            "Could not extract ficha from course name: %s", course_name
        )
        return ""

    def _extract_evidence_headers(self) -> list[Evidence]:
        """Extract evidence definitions from table header <th> elements.

        Only processes <th class="item catlevel2 highlightable ..."> elements.
        Skips "categoryitem" and "courseitem" (totals).
        """
        evidences: list[Evidence] = []

        # Find all <th> that are individual evidence items
        header_ths = self._table.find_all(
            "th",
            class_=lambda c: (
                c
                and "item" in c.split()
                and "catlevel2" in c.split()
                and "highlightable" in c.split()
                and "categoryitem" not in c.split()
                and "courseitem" not in c.split()
            ),
        )

        # Build category map (column index -> category name)
        category_map = self._build_category_map()

        for th in header_ths:
            item_id = self._extract_item_id_from_tag(th)
            if item_id is None:
                continue

            # Extract evidence name from gradeitemheader
            header_elem = th.find(class_="gradeitemheader")
            if header_elem:
                name = header_elem.get_text(strip=True)
            else:
                name = f"Unknown evidence {item_id}"
                logger.warning("No gradeitemheader found for item %d", item_id)

            # Determine category from column index
            col_idx = self._get_column_index(th)
            category = category_map.get(col_idx, "")

            evidences.append(Evidence(
                item_id=item_id,
                name=name,
                category=category,
            ))

        logger.debug("Extracted %d evidence headers", len(evidences))
        return evidences

    def _build_category_map(self) -> dict[int, str]:
        """Build a mapping from column index to category name.

        Category headers (<th class="category catlevel2 statusicons">) have
        colspan attributes that define which data columns they span.
        """
        category_map: dict[int, str] = {}

        cat_headers = self._table.find_all(
            "th",
            class_=lambda c: (
                c
                and "category" in c.split()
                and "catlevel2" in c.split()
                and "statusicons" in c.split()
            ),
        )

        # First 3 columns (c0, c1, c2) are user info, evidence columns start at c3
        current_col = 3

        for cat_th in cat_headers:
            header_elem = cat_th.find(class_="gradeitemheader")
            cat_name = header_elem.get_text(strip=True) if header_elem else ""

            colspan = int(cat_th.get("colspan", 1))

            for col in range(current_col, current_col + colspan):
                category_map[col] = cat_name

            current_col += colspan

        return category_map

    def _extract_students(self, evidence_ids: set[int]) -> list[StudentRow]:
        """Extract all student rows from the grader table."""
        students: list[StudentRow] = []

        user_rows = self._table.find_all("tr", class_="userrow")
        for tr in user_rows:
            student = self._parse_student_row(tr, evidence_ids)
            if student:
                students.append(student)

        logger.debug("Extracted %d student rows", len(students))
        return students

    def _parse_student_row(
        self, tr: Tag, evidence_ids: set[int]
    ) -> StudentRow | None:
        """Parse one <tr class="userrow"> into a StudentRow.

        Structure:
        - data-uid -> user_id
        - <a class="username"> -> full_name (exclude userinitials span)
        - <td class="userusername"> -> document (strip suffix)
        - <td class="useremail"> -> email
        - <td class="gradecell"> -> grade cells
        """
        # User ID
        uid_str = tr.get("data-uid")
        if not uid_str:
            logger.warning("Row without data-uid, skipping")
            return None
        user_id = int(uid_str)

        # Full name
        username_link = tr.find("a", class_="username")
        if username_link:
            # Remove the userinitials span before getting text
            initials_span = username_link.find("span", class_="userinitials")
            if initials_span:
                initials_span.decompose()
            full_name = " ".join(username_link.get_text(strip=True).split())
        else:
            full_name = f"Unknown ({user_id})"

        # Document (cedula)
        username_td = tr.find("td", class_="userusername")
        document = ""
        if username_td:
            content_div = username_td.find(
                "div", attrs={"data-collapse": "content"}
            )
            if content_div:
                raw_username = content_div.get_text(strip=True)
                document = DOCUMENT_SUFFIX_PATTERN.sub("", raw_username)

        # Email
        email_td = tr.find("td", class_="useremail")
        email = ""
        if email_td:
            content_div = email_td.find(
                "div", attrs={"data-collapse": "content"}
            )
            if content_div:
                email = content_div.get_text(strip=True)

        # Grade cells - only process known evidence IDs
        grades: dict[int, GradeCell] = {}
        grade_cells = tr.find_all("td", class_="gradecell")
        for td in grade_cells:
            grade = self._parse_grade_cell(td)
            if grade and grade.evidence_id in evidence_ids:
                grades[grade.evidence_id] = grade

        return StudentRow(
            user_id=user_id,
            full_name=full_name,
            document=document,
            email=email,
            grades=grades,
        )

    def _parse_grade_cell(self, td: Tag) -> GradeCell | None:
        """Parse one <td class="gradecell"> into a GradeCell.

        Structure:
        - data-itemid -> evidence_id
        - <span class="gradevalue"> -> value (A, D, -)
        - "gradepass" in span classes -> passed = True
        """
        item_id = td.get("data-itemid")
        if not item_id:
            item_id = self._extract_item_id_from_tag(td)
            if item_id is None:
                return None
        else:
            item_id = int(item_id)

        # Find the gradevalue span
        grade_span = td.find(
            "span", class_=lambda c: c and "gradevalue" in c
        )
        if not grade_span:
            return None

        # Extract value
        value_text = grade_span.get_text(strip=True)
        try:
            value = GradeStatus(value_text)
        except ValueError:
            logger.warning(
                "Unknown grade value '%s' for item %d", value_text, item_id
            )
            return None

        # Check if passed (has "gradepass" class)
        css_classes = grade_span.get("class", [])
        passed = "gradepass" in css_classes

        return GradeCell(
            evidence_id=item_id,
            value=value,
            passed=passed,
        )

    def compute_summary(self, report: CourseReport) -> CourseSummary:
        """Compute aggregated metrics from a CourseReport."""
        total_approved = 0
        total_disapproved = 0
        total_pending = 0
        pending_by_evidence: dict[int, int] = {
            e.item_id: 0 for e in report.evidences
        }

        for student in report.students:
            for eid, grade in student.grades.items():
                if grade.value == GradeStatus.APPROVED:
                    total_approved += 1
                elif grade.value == GradeStatus.DISAPPROVED:
                    total_disapproved += 1
                elif grade.value == GradeStatus.PENDING:
                    total_pending += 1
                    if eid in pending_by_evidence:
                        pending_by_evidence[eid] += 1

        total_cells = total_approved + total_disapproved + total_pending
        completion_pct = 0.0
        if total_cells > 0:
            completion_pct = round(
                (total_approved + total_disapproved) / total_cells * 100, 1
            )

        return CourseSummary(
            course_id=report.course_id,
            ficha=report.ficha,
            total_students=len(report.students),
            total_evidences=len(report.evidences),
            total_approved=total_approved,
            total_disapproved=total_disapproved,
            total_pending=total_pending,
            pending_by_evidence=pending_by_evidence,
            completion_percentage=completion_pct,
        )

    # --- Helper methods ---

    def _extract_item_id_from_tag(self, tag: Tag) -> int | None:
        """Extract item_id from data-itemid attribute or CSS class."""
        data_id = tag.get("data-itemid")
        if data_id:
            return int(data_id)

        css_class = " ".join(tag.get("class", []))
        match = ITEM_ID_PATTERN.search(css_class)
        if match:
            return int(match.group(1))

        return None

    def _get_column_index(self, th: Tag) -> int:
        """Extract column index from CSS class (e.g., 'cell c3' -> 3)."""
        css_classes = th.get("class", [])
        for cls in css_classes:
            if cls.startswith("c") and cls[1:].isdigit():
                return int(cls[1:])
        return -1
