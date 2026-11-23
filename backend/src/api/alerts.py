"""Alert generation engine for the Zajuna Monitor API."""
from __future__ import annotations

from datetime import date, timedelta

from src.api.schemas import AlertItem
from src.store.cronograma_store import load_cronograma, resolve_evidence_id
from src.store.forum_replies_store import load_forum_replies

# Las alertas de foros solo miran aportes recientes: los de foros de meses
# pasados siguen en la bandeja, pero ya no se pueden responder a tiempo.
FORUM_ALERT_WINDOW_DAYS = 30

# Notas que cuentan como "ya calificada" para ubicar hasta dónde va el curso
_GRADED_VALUES = {"A", "D"}


def load_cutoffs(snapshot: dict) -> dict[str, dict[int, str]]:
    """ficha → {item_id: fecha de cierre YYYY-MM-DD} desde los cronogramas cargados."""
    cutoffs: dict[str, dict[int, str]] = {}
    for course in snapshot.get("courses", []):
        ficha = course.get("ficha")
        data = load_cronograma(ficha) if ficha else None
        if not data:
            continue
        by_item: dict[int, str] = {}
        for entry in data.get("entries", []):
            item_id = entry.get("evidence_item_id") or resolve_evidence_id(
                entry["evidence_name"], snapshot, ficha
            )
            if item_id is not None:
                by_item[item_id] = entry["cutoff_date"]
        cutoffs[ficha] = by_item
    return cutoffs


def _due_item_ids(course: dict, cutoffs: dict[int, str], today: date) -> set[str]:
    """Evidencias que ya deberían tener notas.

    Con fecha de cierre en el cronograma: las que ya cerraron. Sin fecha: las
    que van hasta la última evidencia (en orden del curso) que ya tiene alguna
    nota; las siguientes todavía no se han trabajado.
    """
    evidences = course.get("evidences", [])
    students = course.get("students", [])
    last_graded = -1
    for i, ev in enumerate(evidences):
        key = str(ev["item_id"])
        if any(s.get("grades", {}).get(key, {}).get("value") in _GRADED_VALUES for s in students):
            last_graded = i

    due: set[str] = set()
    for i, ev in enumerate(evidences):
        cutoff = cutoffs.get(ev["item_id"])
        if cutoff is not None:
            if date.fromisoformat(cutoff) <= today:
                due.add(str(ev["item_id"]))
        elif i <= last_graded:
            due.add(str(ev["item_id"]))
    return due


def forum_reply_alerts(ficha: str, today: date) -> list[AlertItem]:
    """Aportes de foro sin réplica con el plazo de 1 día hábil vencido (SAVA 9.1.6).

    Salen de la última revisión guardada de cada foro (Foros → Revisar): no
    entran a Zajuna. El mensaje dice de cuándo es la revisión, porque una
    réplica publicada después no se ve hasta revisar otra vez. Solo cuenta
    aportes de los últimos ``FORUM_ALERT_WINDOW_DAYS`` días.
    """
    # Import tardío: forum_inbox importa los parsers, que no hacen falta para
    # las demás reglas
    from src.api.forum_inbox import count_overdue

    stored = (load_forum_replies(ficha) or {}).get("forums", {})
    alerts: list[AlertItem] = []
    for forum in stored.values():
        overdue = count_overdue(
            forum.get("contributions", []), today, since=today - timedelta(days=FORUM_ALERT_WINDOW_DAYS)
        )
        if overdue == 0:
            continue
        checked = forum.get("checked_at", "")[:10]
        checked_label = f"{checked[8:10]}/{checked[5:7]}" if len(checked) == 10 else "?"
        noun = "aporte" if overdue == 1 else "aportes"
        alerts.append(AlertItem(
            type="forum_reply_overdue",
            severity="critical",
            ficha=ficha,
            message=(
                f"{overdue} {noun} sin réplica del instructor después de 1 día hábil "
                f"en {forum['name']} (revisado el {checked_label})"
            ),
            evidence_name=forum["name"],
            item_id=forum.get("item_id"),
            forum_id=forum["forum_id"],
            pending_count=overdue,
        ))
    return alerts


def generate_alerts(
    snapshot: dict,
    cutoffs: dict[str, dict[int, str]] | None = None,
    today: date | None = None,
) -> list[AlertItem]:
    """Generate alerts from a loaded snapshot dictionary.

    Rules (evidence rules only apply to evidences already due, see
    ``_due_item_ids``; without that filter an ongoing course flags every
    evidence it has not reached yet):
    1. zero_graded (critical): Evidence with 100% pending
    2. high_pending (warning): Evidence with >80% pending (but not 100%)
    3. low_completion (info): Course with <10% completion

    ``cutoffs`` defaults to the stored cronogramas (``load_cutoffs``).
    """
    if cutoffs is None:
        cutoffs = load_cutoffs(snapshot)
    today = today or date.today()
    alerts: list[AlertItem] = []

    courses = snapshot.get("courses", [])
    summaries = snapshot.get("summaries", [])

    # Build summary lookup by course_id
    summary_map: dict[int, dict] = {}
    for s in summaries:
        summary_map[s["course_id"]] = s

    for course in courses:
        course_id = course["course_id"]
        ficha = course["ficha"]
        students = course.get("students", [])
        total_students = len(students)

        if total_students == 0:
            continue

        summary = summary_map.get(course_id, {})

        # Rule 3: low_completion per course
        completion = summary.get("completion_percentage", 0.0)
        if completion < 10.0:
            alerts.append(AlertItem(
                type="low_completion",
                severity="info",
                ficha=ficha,
                message=f"Ficha {ficha} tiene solo {completion}% de avance",
                percentage=completion,
            ))

        # Rules 1 & 2: per-evidence alerts, only for evidences already due
        pending_by_evidence = summary.get("pending_by_evidence", {})
        evidence_map = {str(e["item_id"]): e["name"] for e in course.get("evidences", [])}
        due = _due_item_ids(course, cutoffs.get(ficha, {}), today)

        for item_id_str, pending_count in pending_by_evidence.items():
            if str(item_id_str) not in due:
                continue
            evidence_name = evidence_map.get(str(item_id_str), f"Evidence {item_id_str}")
            pending_pct = (pending_count / total_students) * 100

            if pending_count == total_students:
                # Rule 1: zero_graded (100% pending)
                alerts.append(AlertItem(
                    type="zero_graded",
                    severity="critical",
                    ficha=ficha,
                    message=f"Ninguno de {total_students} aprendices tiene nota en {evidence_name}",
                    evidence_name=evidence_name,
                    item_id=int(item_id_str),
                    pending_count=pending_count,
                    percentage=pending_pct,
                ))
            elif pending_pct > 80:
                # Rule 2: high_pending (>80%)
                alerts.append(AlertItem(
                    type="high_pending",
                    severity="warning",
                    ficha=ficha,
                    message=f"{pending_count} de {total_students} aprendices sin nota en {evidence_name}",
                    evidence_name=evidence_name,
                    item_id=int(item_id_str),
                    pending_count=pending_count,
                    percentage=pending_pct,
                ))

        alerts.extend(forum_reply_alerts(ficha, today))

    # Sort: critical first, then warning, then info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: (severity_order.get(a.severity, 9), -(a.pending_count or 0)))

    return alerts
