"""Data models for the Zajuna scraper."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GradeStatus(str, Enum):
    """Possible values of a grade cell in the Zajuna grader report."""
    APPROVED = "A"
    DISAPPROVED = "D"
    PENDING = "-"


class StudentStatus(str, Enum):
    """Enrollment status of a participant in a Zajuna course."""
    ACTIVE = "Activo"
    SUSPENDED = "Suspendido"


@dataclass
class GradeCell:
    """A single grade value for one student x one evidence."""
    evidence_id: int
    value: GradeStatus
    passed: bool


@dataclass
class Evidence:
    """An evaluable activity (evidence) extracted from grader headers."""
    item_id: int
    name: str
    category: str


@dataclass
class StudentRow:
    """One student's data extracted from a grader report row."""
    user_id: int
    full_name: str
    document: str
    email: str
    grades: dict[int, GradeCell] = field(default_factory=dict)


@dataclass
class CourseReport:
    """Full parsed data from one course's grader report."""
    course_id: int
    course_name: str
    ficha: str
    evidences: list[Evidence] = field(default_factory=list)
    students: list[StudentRow] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=datetime.now)


@dataclass
class CourseSummary:
    """Aggregated metrics for one course."""
    course_id: int
    ficha: str
    total_students: int
    total_evidences: int
    total_approved: int
    total_disapproved: int
    total_pending: int
    pending_by_evidence: dict[int, int] = field(default_factory=dict)
    completion_percentage: float = 0.0


@dataclass
class Participant:
    """One participant from a course's participants page."""
    user_id: int
    full_name: str
    document: str
    email: str
    role: str
    groups: str
    last_access_raw: str
    last_access_days: int
    status: StudentStatus


@dataclass
class CourseParticipants:
    """All participants from one course."""
    course_id: int
    ficha: str
    participants: list[Participant] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=datetime.now)


@dataclass
class ScraperSnapshot:
    """Complete output of one scraper execution."""
    timestamp: datetime
    instructor_id: int
    courses: list[CourseReport] = field(default_factory=list)
    summaries: list[CourseSummary] = field(default_factory=list)
    participants: list[CourseParticipants] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
