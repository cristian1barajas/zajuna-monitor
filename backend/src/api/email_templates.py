"""Email templates for due process stages (plain text, Spanish formal tone)."""
from __future__ import annotations

from src.store.due_process_store import STAGE_LABELS


def generate_email(
    stage: str,
    student_name: str,
    student_document: str,
    ficha: str,
    evidence_names: list[str],
    last_access_info: str = "No disponible",
    history: list[dict] | None = None,
) -> dict:
    """Generate an email draft for a given due process stage.

    Returns dict with: subject, body, stage, stage_label
    """
    generators = {
        "primer_llamado": _primer_llamado,
        "segundo_llamado": _segundo_llamado,
        "plan_mejoramiento": _plan_mejoramiento,
        "comite": _comite,
    }

    fn = generators.get(stage, _primer_llamado)
    subject, body = fn(
        student_name=student_name,
        student_document=student_document,
        ficha=ficha,
        evidence_names=evidence_names,
        last_access_info=last_access_info,
        history=history or [],
    )

    return {
        "subject": subject,
        "body": body,
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
    }


def _format_evidence_list(names: list[str]) -> str:
    """Format evidence names as a numbered list."""
    if not names:
        return "  (Sin evidencias especificadas)"
    return "\n".join(f"  {i}. {name}" for i, name in enumerate(names, 1))


def _format_history_summary(history: list[dict]) -> str:
    """Format history entries as a chronological summary."""
    if not history:
        return ""
    lines = []
    for entry in history:
        date = entry.get("date", "Fecha no registrada")
        if "T" in date:
            date = date.split("T")[0]
        stage_label = STAGE_LABELS.get(entry.get("stage", ""), entry.get("stage", ""))
        lines.append(f"  - {date}: {stage_label}")
    return "\n".join(lines)


def _primer_llamado(
    student_name: str,
    student_document: str,
    ficha: str,
    evidence_names: list[str],
    last_access_info: str,
    history: list[dict],
) -> tuple[str, str]:
    subject = f"Primer llamado de atención - Ficha {ficha} - {student_name}"
    body = f"""Cordial saludo, {student_name}.

Por medio del presente se le notifica que, a la fecha, usted presenta las siguientes evidencias pendientes de entrega en la ficha {ficha}:

{_format_evidence_list(evidence_names)}

Último acceso a la plataforma Zajuna: {last_access_info}
Documento de identidad: {student_document}

Se le recuerda que es su responsabilidad cumplir con la entrega oportuna de las evidencias de aprendizaje. Se le otorga un plazo de dos (2) días hábiles a partir de la fecha de este comunicado para realizar la entrega de las evidencias mencionadas.

De no cumplir con la entrega en el plazo establecido, se procederá con el segundo llamado de atención conforme al debido proceso institucional.

Atentamente,
Instructor de formación
SENA - Ficha {ficha}"""
    return subject, body


def _segundo_llamado(
    student_name: str,
    student_document: str,
    ficha: str,
    evidence_names: list[str],
    last_access_info: str,
    history: list[dict],
) -> tuple[str, str]:
    subject = f"Segundo llamado de atención - Ficha {ficha} - {student_name}"

    history_text = ""
    if history:
        history_text = f"""
Historial del proceso:
{_format_history_summary(history)}
"""

    body = f"""Cordial saludo, {student_name}.

Por medio del presente se le notifica que, pese al primer llamado de atención realizado previamente, usted continúa presentando las siguientes evidencias pendientes de entrega en la ficha {ficha}:

{_format_evidence_list(evidence_names)}

Último acceso a la plataforma Zajuna: {last_access_info}
Documento de identidad: {student_document}
{history_text}
Se le otorga un plazo adicional de dos (2) días hábiles a partir de la fecha de este comunicado para realizar la entrega de las evidencias pendientes.

IMPORTANTE: De no cumplir con la entrega en el plazo establecido, se procederá con la elaboración de un Plan de Mejoramiento, el cual deberá ser firmado por usted y contará con copia a la coordinación académica.

Atentamente,
Instructor de formación
SENA - Ficha {ficha}"""
    return subject, body


def _plan_mejoramiento(
    student_name: str,
    student_document: str,
    ficha: str,
    evidence_names: list[str],
    last_access_info: str,
    history: list[dict],
) -> tuple[str, str]:
    subject = f"Plan de mejoramiento - Ficha {ficha} - {student_name}"

    history_text = ""
    if history:
        history_text = f"""
Historial del debido proceso:
{_format_history_summary(history)}
"""

    body = f"""Cordial saludo, {student_name}.

Tras haber agotado dos llamados de atención sin que se haya dado cumplimiento a la entrega de las evidencias requeridas, se procede a la formalización de un Plan de Mejoramiento para la ficha {ficha}.

Evidencias pendientes de entrega:

{_format_evidence_list(evidence_names)}

Último acceso a la plataforma Zajuna: {last_access_info}
Documento de identidad: {student_document}
{history_text}
El Plan de Mejoramiento deberá ser firmado por usted como constancia de su compromiso. Se le otorga un plazo de tres (3) días hábiles a partir de la firma del plan para realizar la entrega de las evidencias mencionadas.

De no cumplir con los compromisos establecidos en el Plan de Mejoramiento, su caso será remitido al Comité de Evaluación y Seguimiento de su programa de formación.

CC: Coordinación Académica

Atentamente,
Instructor de formación
SENA - Ficha {ficha}"""
    return subject, body


def _comite(
    student_name: str,
    student_document: str,
    ficha: str,
    evidence_names: list[str],
    last_access_info: str,
    history: list[dict],
) -> tuple[str, str]:
    subject = f"Remisión a Comité de Evaluación - Ficha {ficha} - {student_name}"

    history_text = ""
    if history:
        history_text = f"""
Historial completo del debido proceso:
{_format_history_summary(history)}
"""

    body = f"""Cordial saludo.

Por medio del presente se solicita la remisión del caso del aprendiz {student_name} (documento {student_document}) al Comité de Evaluación y Seguimiento de la ficha {ficha}.

Se han agotado todas las instancias del debido proceso (primer llamado de atención, segundo llamado de atención y plan de mejoramiento) sin que el aprendiz haya cumplido con la entrega de las evidencias requeridas.

Evidencias pendientes de entrega:

{_format_evidence_list(evidence_names)}

Último acceso a la plataforma Zajuna: {last_access_info}
Documento de identidad: {student_document}
{history_text}
Se solicita al Comité de Evaluación y Seguimiento que evalúe el caso y determine las acciones a seguir conforme a la normatividad vigente del SENA.

Atentamente,
Instructor de formación
SENA - Ficha {ficha}"""
    return subject, body
