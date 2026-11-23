"""Report engine: cross selected evidence_ids vs student grades."""
from __future__ import annotations

from src.models.schemas import GradeStatus
from src.store.cached_json import read_json_cached


def _load_submission_status(ficha: str) -> set[str]:
    """Load the submission status cache and return the set of pending_cells.

    Each entry is "item_id:user_id" for cells that have been submitted
    but not yet graded (yellow cells).

    Cached by mtime (read_json_cached). The writer lives in
    routes/pending_grading.py and does not call invalidate(); the new
    mtime after each refresh invalidates the entry naturally.
    """
    from src.config import SUBMISSION_STATUS_DIR
    from src.store.instructor_scope import scoped_dir

    path = scoped_dir(SUBMISSION_STATUS_DIR) / f"{ficha}.json"
    try:
        data = read_json_cached(path, default=None)
        if data is None:
            return set()
        return set(data.get("pending_cells", []))
    except Exception:
        return set()


def generate_report(snapshot: dict, ficha: str, evidence_ids: list[int]) -> dict:
    """Generate an overdue report for a ficha with selected evidence IDs.

    Returns a dict with:
      - ficha, selected_evidences_count, total_students_with_overdue
      - students: list of students with at least one overdue evidence
      - Each student includes: overdue_evidences list, overdue_count, activity data
    """
    # Find the course
    course = None
    for c in snapshot.get("courses", []):
        if c.get("ficha") == ficha:
            course = c
            break

    if course is None:
        return {
            "ficha": ficha,
            "selected_evidences_count": len(evidence_ids),
            "total_students_with_overdue": 0,
            "total_students": 0,
            "students": [],
        }

    # Build evidence name/category lookup
    evidence_info = {}
    for ev in course.get("evidences", []):
        evidence_info[ev["item_id"]] = {
            "name": ev["name"],
            "category": ev["category"],
        }

    # Find participant data (for status, last_access)
    participant_map: dict[int, dict] = {}
    for cp in snapshot.get("participants", []):
        if cp.get("ficha") == ficha:
            for p in cp.get("participants", []):
                participant_map[p["user_id"]] = p
            break

    # Load submission status to exclude yellow cells (submitted but ungraded)
    submitted_cells = _load_submission_status(ficha)

    # Cross grades vs selected evidence_ids
    all_students = []

    for student in course.get("students", []):
        overdue = []
        user_id = student["user_id"]
        for eid in evidence_ids:
            grade = student.get("grades", {}).get(str(eid))
            if grade is None:
                continue
            value = grade.get("value")
            # Skip approved
            if value == GradeStatus.APPROVED.value:
                continue
            # Pending: check if it's a yellow cell (submitted but ungraded)
            if value == GradeStatus.PENDING.value:
                cell_key = f"{eid}:{user_id}"
                if cell_key in submitted_cells:
                    continue  # Yellow cell → exclude
                info = evidence_info.get(eid, {})
                overdue.append({
                    "item_id": eid,
                    "name": info.get("name", f"Evidence {eid}"),
                    "category": info.get("category", ""),
                })
            # Disapproved: include
            elif value == GradeStatus.DISAPPROVED.value:
                info = evidence_info.get(eid, {})
                overdue.append({
                    "item_id": eid,
                    "name": info.get("name", f"Evidence {eid}"),
                    "category": info.get("category", ""),
                })

        # Merge participant data
        participant = participant_map.get(student["user_id"], {})

        all_students.append({
            "user_id": student["user_id"],
            "full_name": student["full_name"],
            "document": student["document"],
            "email": student["email"],
            "status": participant.get("status", "Desconocido"),
            "last_access_days": participant.get("last_access_days", -1),
            "last_access_raw": participant.get("last_access_raw", ""),
            "overdue_evidences": overdue,
            "overdue_count": len(overdue),
        })

    # Sort by overdue_count descending (students with 0 go to the end)
    all_students.sort(key=lambda s: -s["overdue_count"])

    total_with_overdue = sum(1 for s in all_students if s["overdue_count"] > 0)

    return {
        "ficha": ficha,
        "selected_evidences_count": len(evidence_ids),
        "total_students_with_overdue": total_with_overdue,
        "total_students": len(all_students),
        "students": all_students,
    }
