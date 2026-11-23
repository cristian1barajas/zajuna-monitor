"""Acta de reunión del equipo ejecutor con la relación de llamados enviados un día.

Se llena ``templates/acta_equipo_ejecutor.docx`` (formato SENA del acta, sin
firmas ni datos) por código: los textos salen de las etapas y los aprendices
registrados ese día, no de una redacción libre. La plantilla trae un párrafo
prototipo por tipo (``{{H}}`` subtítulo numerado, ``{{B}}`` viñeta, ...) que se
clona para conservar el formato del acta original.
"""
from __future__ import annotations

import copy
import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from src.config import BASE_DIR
from src.outlook.llamados import fold

TEMPLATE_PATH = BASE_DIR / "templates" / "acta_equipo_ejecutor.docx"

_MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# Orden del debido proceso y textos por etapa.
STAGE_ORDER = ["primer_llamado", "segundo_llamado", "tercer_llamado", "plan_mejoramiento", "comite"]
STAGE_LABELS = {
    "primer_llamado": "Primer llamado de atención",
    "segundo_llamado": "Segundo llamado de atención",
    "tercer_llamado": "Tercer llamado de atención",
    "plan_mejoramiento": "Plan de mejoramiento",
    "comite": "Remisión a Comité de Evaluación",
}
STAGE_SHORT = {
    "primer_llamado": "1er llamado",
    "segundo_llamado": "2do llamado",
    "tercer_llamado": "3er llamado",
    "plan_mejoramiento": "Plan de mejoramiento",
    "comite": "Comité de Evaluación",
}
_STAGE_COUNT = {
    "primer_llamado": ("primer llamado de atención", "primeros llamados de atención"),
    "segundo_llamado": ("segundo llamado de atención", "segundos llamados de atención"),
    "tercer_llamado": ("tercer llamado de atención", "terceros llamados de atención"),
    "plan_mejoramiento": ("plan de mejoramiento", "planes de mejoramiento"),
    "comite": ("remisión a Comité de Evaluación", "remisiones a Comité de Evaluación"),
}
_STAGE_AGENDA = {
    "primer_llamado": "Aprobación del primer llamado de atención por incumplimiento en la entrega de evidencias, conforme al Acuerdo 009 de 2024.",
    "segundo_llamado": "Aprobación del segundo llamado de atención por incumplimiento reiterado en la entrega de evidencias, conforme al Acuerdo 009 de 2024.",
    "tercer_llamado": "Aprobación del tercer llamado de atención por incumplimiento reiterado en la entrega de evidencias, conforme al Acuerdo 009 de 2024.",
    "plan_mejoramiento": "Aprobación del plan de mejoramiento para los aprendices que no regularizaron su situación tras el segundo llamado de atención.",
    "comite": "Remisión al Comité de Evaluación y Seguimiento de los aprendices que agotaron las instancias del debido proceso.",
}
_STAGE_DECISION = {
    "primer_llamado": "aprobó la emisión del primer llamado de atención",
    "segundo_llamado": "aprobó la emisión del segundo llamado de atención",
    "tercer_llamado": "aprobó la emisión del tercer llamado de atención",
    "plan_mejoramiento": "aprobó la formulación de un plan de mejoramiento",
    "comite": "aprobó la remisión al Comité de Evaluación y Seguimiento",
}
_STAGE_FOLLOWUP = {
    "primer_llamado": "Los aprendices cuentan con el plazo indicado en la notificación para entregar las evidencias pendientes; de no hacerlo, se continuará con el segundo llamado de atención.",
    "segundo_llamado": "De no regularizar la entrega de evidencias en el plazo indicado, se continuará con el plan de mejoramiento.",
    "tercer_llamado": "De no regularizar la entrega de evidencias en el plazo indicado, se continuará con el plan de mejoramiento.",
    "plan_mejoramiento": "El plan de mejoramiento enviado a cada aprendiz relaciona las evidencias pendientes y el plazo para entregarlas.",
    "comite": "Se agotaron las instancias previas del debido proceso (primer llamado, segundo llamado y plan de mejoramiento) sin que los aprendices entregaran las evidencias requeridas.",
}
_STAGE_COMMITMENT = {
    "primer_llamado": "Hacer seguimiento a la entrega de evidencias de los aprendices con primer llamado de atención.",
    "segundo_llamado": "Hacer seguimiento a la entrega de evidencias de los aprendices con segundo llamado de atención.",
    "tercer_llamado": "Hacer seguimiento a la entrega de evidencias de los aprendices con tercer llamado de atención.",
    "plan_mejoramiento": "Verificar el cumplimiento de los planes de mejoramiento dentro de los plazos establecidos.",
    "comite": "Remitir a coordinación los casos para el Comité de Evaluación y Seguimiento, con los soportes del debido proceso.",
}


def long_date(d: date) -> str:
    return f"{d.day} de {_MONTHS[d.month - 1]} de {d.year}"


@dataclass(frozen=True)
class Asistente:
    nombre: str
    dependencia: str = "SENA/CMM"


@dataclass(frozen=True)
class LlamadoActa:
    nombre: str
    documento: str
    stage: str
    hora_envio: str = ""  # "12:33 p. m." si hay soporte de Outlook


@dataclass
class ActaInput:
    numero: str
    ficha: str
    fecha_envio: date
    fecha_acta: date
    hora_inicio: str
    hora_fin: str
    asistentes: list[Asistente]
    llamados: list[LlamadoActa]
    anexo_zip: str = ""
    soportes: int = 0


def _count_phrase(stage: str, n: int) -> str:
    one, many = _STAGE_COUNT[stage]
    return f"{n} {one if n == 1 else many}"


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def _set_text(p, text: str, bold_prefix: str = "") -> None:
    runs = p.runs
    first = runs[0] if runs else p.add_run()
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    if bold_prefix:
        first.text = bold_prefix
        first.bold = True
        rest = copy.deepcopy(first._r)
        first._r.addnext(rest)
        p.runs[1].text = text
        p.runs[1].bold = False
    else:
        first.text = text


def _find(cell, marker: str):
    for p in cell.paragraphs:
        if p.text.strip() == marker:
            return p
    raise ValueError(f"La plantilla del acta no tiene {marker}")


def _replace_marker(doc, marker: str, text: str) -> None:
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if marker in p.text:
                        full = p.text.replace(marker, text)
                        _set_text(p, full)


class _CellWriter:
    """Reescribe una celda clonando párrafos prototipo, en orden."""

    def __init__(self, cell, prototypes: dict[str, object]):
        self.cell = cell
        self.protos = {k: copy.deepcopy(p._p) for k, p in prototypes.items()}
        for p in list(cell.paragraphs):
            p._p.getparent().remove(p._p)

    def add(self, kind: str, text: str = "", bold_prefix: str = "") -> None:
        el = copy.deepcopy(self.protos[kind])
        self.cell._tc.append(el)
        p = self.cell.paragraphs[-1]
        _set_text(p, text, bold_prefix)


def _cell(table, row: int):
    return table.rows[row].cells[0]


def _borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "808080")
        borders.append(el)
    tbl_pr.append(borders)


def _shade(cell, fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)


def _llamados_table(cell, llamados: list[LlamadoActa]) -> None:
    headers = ["No.", "Aprendiz", "Documento", "Etapa", "Hora de envío"]
    widths = [Cm(1.0), Cm(6.6), Cm(2.6), Cm(3.4), Cm(2.4)]
    table = cell.add_table(rows=1 + len(llamados), cols=len(headers))
    _borders(table)
    rows = [headers] + [
        [str(i), ll.nombre, ll.documento or "—", STAGE_SHORT.get(ll.stage, ll.stage), ll.hora_envio or "—"]
        for i, ll in enumerate(llamados, 1)
    ]
    # La fila de títulos se repite si la tabla pasa de página.
    header_pr = table.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    header_pr.append(repeat)
    for r, values in enumerate(rows):
        for c, value in enumerate(values):
            tc = table.rows[r].cells[c]
            tc.width = widths[c]
            p = tc.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            if c in (0, 2, 4):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(value)
            run.font.size = Pt(9)
            run.bold = r == 0
            if r == 0:
                _shade(tc, "E7F3DD")
    # Una celda de Word debe terminar en párrafo.
    cell.add_paragraph()


def build_acta(data: ActaInput, template: Path = TEMPLATE_PATH) -> bytes:
    if not data.llamados:
        raise ValueError("No hay llamados para el acta")
    doc = Document(str(template))
    main, people = doc.tables[0], doc.tables[1]
    fecha_envio = long_date(data.fecha_envio)
    stages = [s for s in STAGE_ORDER if any(ll.stage == s for ll in data.llamados)]
    counts = {s: sum(1 for ll in data.llamados if ll.stage == s) for s in stages}
    resumen = _join([_count_phrase(s, counts[s]) for s in stages])

    _replace_marker(doc, "{{NUMERO}}", data.numero)
    _replace_marker(doc, "{{FECHA}}", long_date(data.fecha_acta))
    _replace_marker(doc, "{{HORA_INICIO}}", data.hora_inicio)
    _replace_marker(doc, "{{HORA_FIN}}", data.hora_fin)

    # Agenda
    agenda_cell = _cell(main, 4)
    w = _CellWriter(agenda_cell, {"label": agenda_cell.paragraphs[0], "b": _find(agenda_cell, "{{AGENDA}}")})
    w.add("label", "AGENDA O PUNTOS PARA DESARROLLAR:")
    w.add("b", f"Revisión del seguimiento académico de la ficha {data.ficha}.")
    for s in stages:
        w.add("b", _STAGE_AGENDA[s])
    w.add("b", f"Relación de las notificaciones enviadas por correo electrónico el {fecha_envio}.")
    w.add("b", "Compromisos y seguimiento a los aprendices notificados.")

    # Objetivo
    _replace_marker(
        doc,
        "{{OBJETIVO}}",
        f"La reunión tuvo como propósito revisar el seguimiento académico de la ficha {data.ficha} "
        f"y formalizar las acciones del debido proceso aplicadas el {fecha_envio}, en el marco del "
        f"Acuerdo 009 de 2024: {resumen}. Cada aprendiz fue notificado por correo electrónico desde "
        "la cuenta institucional del instructor y los soportes de envío se relacionan como anexo de la presente acta.",
    )

    # Desarrollo
    dev = _cell(main, 6)
    w = _CellWriter(
        dev,
        {
            "empty": dev.paragraphs[0],
            "label": dev.paragraphs[1],
            "h": _find(dev, "{{H}}"),
            "b": _find(dev, "{{B}}"),
            "title": _find(dev, "{{TITULO}}"),
            "label2": next(p for p in dev.paragraphs if p.text.startswith("COMPROMISOS")),
            "c": _find(dev, "{{COMPROMISO}}"),
        },
    )
    w.add("empty")
    w.add("label", "DESARROLLO DE LA REUNIÓN")
    w.add("empty")
    w.add("h", "Seguimiento académico de la ficha")
    w.add("b", f"Se revisó el estado de entrega de evidencias de los aprendices de la ficha {data.ficha} con corte al {fecha_envio}.")
    w.add(
        "b",
        f"Se identificaron {len(data.llamados)} aprendices con incumplimiento en la entrega de evidencias "
        "que requieren la siguiente etapa del debido proceso.",
    )
    w.add("empty")
    for s in stages:
        n = counts[s]
        w.add("h", STAGE_LABELS[s])
        w.add(
            "b",
            f"El equipo ejecutor revisó uno a uno los casos y {_STAGE_DECISION[s]} "
            f"para {n} {'aprendiz' if n == 1 else 'aprendices'}.",
        )
        w.add("b", f"La notificación se envió a cada aprendiz por correo electrónico el {fecha_envio}.")
        w.add("b", _STAGE_FOLLOWUP[s])
        w.add("empty")
    w.add("h", "Relación de notificaciones enviadas")
    w.add("b", f"A continuación se relacionan los aprendices notificados el {fecha_envio}, con la etapa del debido proceso y la hora de envío del correo.")
    w.add("empty")
    w.add("title", f"RELACIÓN DE LLAMADOS DE ATENCIÓN ENVIADOS EL {fecha_envio.upper()} - FICHA {data.ficha}")
    _llamados_table(dev, data.llamados)
    w.add("label2", "COMPROMISOS Y PRÓXIMOS PASOS")
    for s in stages:
        w.add("c", _STAGE_COMMITMENT[s], bold_prefix="Equipo ejecutor: ")
    w.add("c", "Revisar en la próxima reunión el cumplimiento de los aprendices notificados y definir la siguiente etapa del debido proceso conforme al Acuerdo 009 de 2024.", bold_prefix="Equipo completo: ")
    w.add("empty")

    # Asistentes: una fila por instructor, firma en blanco.
    proto = people.rows[0]._tr
    anchor = proto
    for _ in data.asistentes:
        tr = copy.deepcopy(proto)
        anchor.addnext(tr)
        anchor = tr
    proto.getparent().remove(proto)
    for i, a in enumerate(data.asistentes):
        row = people.rows[i]
        for p in row.cells[0].paragraphs:
            if "{{NOMBRE}}" in p.text:
                _set_text(p, a.nombre)
        for p in row.cells[1].paragraphs:
            if "{{DEPENDENCIA}}" in p.text:
                _set_text(p, a.dependencia)

    anexo = (
        f"Soportes de las notificaciones enviadas el {fecha_envio}: {data.soportes} correos impresos "
        f"desde Outlook en PDF ({data.anexo_zip})."
        if data.soportes
        else f"Correos de notificación enviados a los aprendices el {fecha_envio}."
    )
    _replace_marker(doc, "{{ANEXOS}}", anexo)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def acta_filename(fecha_acta: date) -> str:
    """Mismo nombre que las actas del instructor: ``ACTA_EQUIPO_EJECUTOR_15-09-26.docx`` (fecha del acta)."""
    return f"ACTA_EQUIPO_EJECUTOR_{fecha_acta:%d-%m-%y}.docx"


def _key(name: str) -> str:
    return " ".join(fold(name).split())


def _hora(iso: str) -> str:
    sent = datetime.fromisoformat(iso)
    return sent.strftime("%I:%M %p").lstrip("0").replace("AM", "a. m.").replace("PM", "p. m.")


def collect_llamados(
    due_records: list[dict],
    soportes: list[dict],
    fecha_envio: date,
    documentos: dict[str, str] | None = None,
) -> tuple[list[LlamadoActa], list[dict]]:
    """Llamados de ese día: lo registrado en Debido proceso, con la hora real del correo si hay soporte.

    También entran los correos con soporte que no se registraron en la app
    (el documento se busca por nombre en ``documentos``). Devuelve los
    llamados en orden de etapa y nombre, y los soportes de ese día.
    """
    day = fecha_envio.isoformat()
    del_dia = [s for s in soportes if s.get("sent_at", "")[:10] == day]
    by_key = {(_key(s["student_name"]), s["stage"]): s for s in del_dia}
    llamados: dict[tuple[str, str], LlamadoActa] = {}
    for rec in due_records:
        for h in rec.get("history", []):
            if h.get("date", "")[:10] != day:
                continue
            k = (_key(rec["full_name"]), h["stage"])
            soporte = by_key.get(k)
            llamados[k] = LlamadoActa(
                nombre=rec["full_name"],
                documento=rec.get("document", ""),
                stage=h["stage"],
                hora_envio=_hora(soporte["sent_at"]) if soporte else "",
            )
    for k, s in by_key.items():
        if k not in llamados and s["stage"] in STAGE_ORDER:
            llamados[k] = LlamadoActa(
                nombre=s["student_name"],
                documento=(documentos or {}).get(k[0], ""),
                stage=s["stage"],
                hora_envio=_hora(s["sent_at"]),
            )
    ordered = sorted(llamados.values(), key=lambda ll: (STAGE_ORDER.index(ll.stage), _key(ll.nombre)))
    return ordered, del_dia
