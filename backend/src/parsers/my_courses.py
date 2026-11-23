"""Parser for the "Mis cursos" navigation block of Zajuna's /zajuna/my/ page.

The login flow already downloads /zajuna/my/ (AuthManager step 3). Its
navigation block lists the instructor's courses, one node per course:

    <li class="type_course depth_3 contains_branch" data-node-key="89977" ...>
      <p class="tree_item branch">
        <a title="ANALISIS Y DESARROLLO DE SOFTWARE. (3388997) "
           href="https://zajuna.sena.edu.co/zajuna/course/view.php?id=89977">
          P_228118_V_3388997_R_11_C_9214</a>
      </p>
    </li>

The shortname encodes program and ficha:
    P_<program_code>_V_<ficha>_R_<n>_C_<centro>
e.g. 228118 = Análisis y Desarrollo de Software (ADSO),
     233104 = Programación de Software (TPS).

Moodle caps this block at ``navcourselimit`` courses and then appends a
"Más..." node; ``truncated`` reports it so the caller can warn the user.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_COURSE_HREF_PATTERN = re.compile(r"/course/view\.php\?id=(\d+)")
_SHORTNAME_PATTERN = re.compile(r"^P_(\d+)_V_(\d{7})_R_\d+_C_\d+$")
_FICHA_IN_TITLE_PATTERN = re.compile(r"\((\d{7})\)")
_MORE_LINK_TEXTS = {"más...", "mas...", "more..."}


@dataclass
class DiscoveredCourse:
    """A course listed in the instructor's "Mis cursos" block."""

    course_id: int
    shortname: str
    fullname: str  # Without the trailing "(ficha)", e.g. "PROGRAMACION DE SOFTWARE"
    ficha: str  # 7 digits, or "" when neither shortname nor title carry it
    program_code: str  # e.g. "228118", or "" when the shortname is non-standard


@dataclass
class MyCoursesResult:
    courses: list[DiscoveredCourse]
    truncated: bool  # True if Moodle hid courses behind a "Más..." link


def parse_my_courses(html: str) -> MyCoursesResult:
    """Extract the instructor's courses from the /zajuna/my/ HTML.

    Courses are deduplicated by course_id (a course can appear both under
    "Mis cursos" and as the current course). Returns an empty list when the
    block is missing; the caller decides whether that is an error.
    """
    soup = BeautifulSoup(html, "lxml")

    courses: dict[int, DiscoveredCourse] = {}
    for node in soup.select("li.type_course"):
        link = node.find("a", href=_COURSE_HREF_PATTERN)
        if link is None:
            continue
        course_id = int(_COURSE_HREF_PATTERN.search(link["href"]).group(1))
        if course_id in courses:
            continue
        courses[course_id] = _build_course(
            course_id,
            shortname=link.get_text(strip=True),
            title=(link.get("title") or "").strip(),
        )

    truncated = any(
        a.get_text(strip=True).lower() in _MORE_LINK_TEXTS for a in soup.find_all("a")
    )

    without_ficha = [c.course_id for c in courses.values() if not c.ficha]
    if without_ficha:
        logger.warning("Cursos sin número de ficha en Mis cursos: %s", without_ficha)
    logger.info(
        "Mis cursos: %d cursos encontrados%s",
        len(courses),
        " (lista truncada por Moodle)" if truncated else "",
    )
    return MyCoursesResult(courses=list(courses.values()), truncated=truncated)


def _build_course(course_id: int, shortname: str, title: str) -> DiscoveredCourse:
    program_code = ""
    ficha = ""
    match = _SHORTNAME_PATTERN.match(shortname)
    if match:
        program_code, ficha = match.group(1), match.group(2)
    else:
        title_match = _FICHA_IN_TITLE_PATTERN.search(title)
        if title_match:
            ficha = title_match.group(1)

    fullname = _FICHA_IN_TITLE_PATTERN.sub("", title).strip().rstrip(".").strip()
    return DiscoveredCourse(
        course_id=course_id,
        shortname=shortname,
        fullname=fullname or shortname,
        ficha=ficha,
        program_code=program_code,
    )
