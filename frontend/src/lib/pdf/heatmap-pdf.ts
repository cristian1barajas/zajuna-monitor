/**
 * Generador del documento HTML de exportación PDF del heatmap de
 * evidencias (fichas). Función pura: recibe los datos ya filtrados
 * y devuelve el HTML listo para imprimir.
 */

import type { StudentItem, EvidenceItem } from "@/types/api";
import { gradeHex } from "@/lib/status-colors";
import { extractGACode } from "@/lib/grading";

export interface HeatmapPdfParams {
  /** Número de ficha (para título y encabezados). */
  ficha?: string;
  /** Nombre del programa de formación. */
  courseName?: string;
  /** Filtro de etapa activo al exportar. */
  evidenceFilter: "all" | "lectiva" | "productiva";
  /** Total de aprendices de la ficha (sin filtrar). */
  totalStudents: number;
  /** Aprendices que van al PDF (ya filtrados, ordenados y sin excluidos). */
  students: StudentItem[];
  /** Evidencias que van al PDF (ya filtradas y sin excluidas). */
  evidences: EvidenceItem[];
  /** Celdas "item_id:user_id" entregadas sin calificar (amarillo). */
  pendingCells: Set<string>;
  /** Incluir la página de listado de pendientes por aprendiz. */
  includeDetail: boolean;
}

/** Construye el HTML completo del PDF del mapa de calor de evidencias. */
export function buildHeatmapPdfHtml(params: HeatmapPdfParams): string {
  const {
    ficha,
    courseName,
    evidenceFilter,
    totalStudents,
    students: studentsForPDF,
    evidences: evForPDF,
    pendingCells,
    includeDetail,
  } = params;

  const today = new Date().toLocaleDateString("es-CO", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const etapaLabel =
    evidenceFilter === "lectiva"
      ? " (Etapa Lectiva)"
      : evidenceFilter === "productiva"
        ? " (Etapa Productiva)"
        : "";
  const title = courseName
    ? `Mapa de Calor - Ficha ${ficha} - ${courseName}${etapaLabel}`
    : `Mapa de Calor - Ficha ${ficha}${etapaLabel}`;

  const cellSize = 15;
  const cellGap = 2;
  const nameWidth = 230;
  const headerHeight = 130;

  const gaCodes = evForPDF.map((ev) => extractGACode(ev.name));

  const pendingByStudent = studentsForPDF.map((student) => {
    const pending: string[] = [];
    for (const ev of evForPDF) {
      const grade = student.grades[String(ev.item_id)];
      const value = grade?.value ?? "-";
      if (value === "-") {
        pending.push(extractGACode(ev.name));
      }
    }
    return { name: student.full_name, status: student.status, pending };
  });

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${title}</title>
  <style>
    /* Page 1: Heatmap in landscape, full width */
    @page { size: landscape; margin: 15mm 12mm; }

    * { box-sizing: border-box; }
    body {
      /* Work Sans = tipografía institucional SENA; Calibri = secundaria para documentos */
      font-family: 'Work Sans', 'Calibri', 'Segoe UI', Arial, sans-serif;
      margin: 0;
      padding: 0;
      color: #1a1a1a;
    }

    /* ── Heatmap page ── */
    .heatmap-page {
      padding: 0;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
      padding-bottom: 10px;
      border-bottom: 2px solid #39A900;
    }
    .header h1 {
      font-size: 15px;
      font-weight: 700;
      color: #00324D;
      margin: 0 0 3px 0;
    }
    .header .subtitle {
      font-size: 10px;
      color: #6B6B6B;
      margin: 0;
    }
    .header .badge {
      background: #39A900;
      color: white;
      font-size: 9px;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 12px;
      white-space: nowrap;
    }

    .legend {
      display: flex;
      gap: 16px;
      margin-bottom: 10px;
      font-size: 9px;
      color: #4A4A4A;
    }
    .legend-item { display: flex; align-items: center; gap: 4px; }
    .legend-box { width: 12px; height: 12px; border-radius: 3px; }

    /* Heatmap table */
    table.heatmap { border-collapse: separate; border-spacing: ${cellGap}px; }
    table.heatmap th, table.heatmap td { padding: 0; }
    table.heatmap th.ga-header {
      width: ${cellSize}px;
      height: ${headerHeight}px;
      vertical-align: bottom;
      text-align: center;
    }
    table.heatmap th.ga-header span {
      writing-mode: vertical-rl;
      transform: rotate(180deg);
      display: inline-block;
      white-space: nowrap;
      font-size: 9px;
      font-weight: 500;
      color: #6B6B6B;
      line-height: ${cellSize}px;
    }
    table.heatmap td.name-cell {
      width: ${nameWidth}px;
      max-width: ${nameWidth}px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      padding-right: 6px;
      font-size: 8px;
      font-weight: 500;
      color: #1A1A1A;
    }
    table.heatmap td.name-cell.suspended {
      text-decoration: line-through;
      color: #B5B5B5;
      font-weight: 400;
    }
    table.heatmap td.grade-cell {
      width: ${cellSize}px;
      height: ${cellSize}px;
      min-width: ${cellSize}px;
      border-radius: 3px;
    }
    .heatmap-footer {
      margin-top: 8px;
      font-size: 9px;
      color: #6B6B6B;
      text-align: right;
    }

    /* ── Pending page (letter, portrait) ── */
    .pending-page {
      page-break-before: always;
      padding: 0;
    }
    .pending-page .header {
      margin-bottom: 16px;
    }
    .pending-page h2 {
      font-size: 14px;
      font-weight: 700;
      color: #00324D;
      margin: 0 0 4px 0;
    }
    .pending-page .subtitle {
      font-size: 10px;
      color: #6B6B6B;
      margin: 0;
    }
    .pending-list {
      columns: 2;
      column-gap: 24px;
      font-size: 9px;
    }
    .pending-item {
      break-inside: avoid;
      margin-bottom: 10px;
      padding: 6px 8px;
      background: #F8F8F6;
      border-radius: 6px;
      border: 1px solid #E2E2DD;
    }
    .pending-item .student-name {
      font-weight: 600;
      font-size: 9px;
      color: #1A1A1A;
      margin-bottom: 2px;
    }
    .pending-item .student-name.suspended {
      text-decoration: line-through;
      color: #B5B5B5;
    }
    .pending-item .count-badge {
      display: inline-block;
      background: #39A900;
      color: white;
      font-size: 7px;
      font-weight: 600;
      padding: 1px 5px;
      border-radius: 8px;
      margin-left: 4px;
    }
    .pending-codes {
      color: #6B6B6B;
      font-size: 8px;
      line-height: 1.4;
    }

    @media print {
      body { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
      table.heatmap td.grade-cell { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    }
    table.heatmap td.grade-cell[style] { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  </style>
</head>
<body>
  <!-- PAGE 1: Heatmap (Landscape) -->
  <div class="heatmap-page">
    <div class="header">
      <div>
        <h1>${title}</h1>
        <p class="subtitle">Fecha: ${today} | ${studentsForPDF.length} de ${totalStudents} aprendices x ${evForPDF.length} evidencias</p>
      </div>
      <div class="badge">ZAJUNA MONITOR</div>
    </div>

    <div class="legend">
      <div class="legend-item"><div class="legend-box" style="background:${gradeHex("A")}"></div> Aprobado (A)</div>
      <div class="legend-item"><div class="legend-box" style="background:${gradeHex("D")}"></div> Desaprobado (D)</div>
      <div class="legend-item"><div class="legend-box" style="background:${gradeHex("-")}"></div> Pendiente (-)</div>
      ${pendingCells.size > 0 ? `<div class="legend-item"><div class="legend-box" style="background:${gradeHex("-", true)}"></div> Enviado sin calificar</div>` : ""}
    </div>

    <table class="heatmap">
      <thead>
        <tr>
          <th style="width:${nameWidth}px"></th>
          ${gaCodes.map((code) => `<th class="ga-header"><span>${code}</span></th>`).join("")}
        </tr>
      </thead>
      <tbody>
        ${studentsForPDF
          .map((student) => {
            const isSuspended = student.status === "Suspendido";
            const cells = evForPDF
              .map((ev) => {
                const grade = student.grades[String(ev.item_id)];
                const value = grade?.value ?? "-";
                const isSubmitted = pendingCells.has(`${ev.item_id}:${student.user_id}`);
                return `<td class="grade-cell" style="background-color:${gradeHex(value, isSubmitted)} !important"></td>`;
              })
              .join("");
            return `<tr>
              <td class="name-cell ${isSuspended ? "suspended" : ""}">${student.full_name}${isSuspended ? " (S)" : ""}</td>
              ${cells}
            </tr>`;
          })
          .join("")}
      </tbody>
    </table>
    <div class="heatmap-footer">Generado por Zajuna Monitor</div>
  </div>

  ${includeDetail ? `<!-- PAGE 2+: Pending evidences (Letter Portrait) -->
  <div class="pending-page">
    <div class="header">
      <div>
        <h2>Evidencias Pendientes por Aprendiz</h2>
        <p class="subtitle">Ficha ${ficha}${etapaLabel} | ${today}</p>
      </div>
      <div class="badge">ZAJUNA MONITOR</div>
    </div>
    <div class="pending-list">
      ${pendingByStudent
        .filter((s) => s.pending.length > 0)
        .map(
          (s) => `<div class="pending-item">
            <div class="student-name ${s.status === "Suspendido" ? "suspended" : ""}">${s.name}${s.status === "Suspendido" ? " (Suspendido)" : ""}<span class="count-badge">${s.pending.length}</span></div>
            <div class="pending-codes">${s.pending.join(", ")}</div>
          </div>`
        )
        .join("")}
    </div>
  </div>` : ""}
</body>
</html>`;
}
