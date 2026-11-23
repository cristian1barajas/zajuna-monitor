/**
 * Generador del documento HTML de exportación PDF del heatmap de
 * juicios evaluativos (RAPs). Función pura: recibe los datos ya
 * filtrados y devuelve el HTML listo para imprimir.
 */

import type { StudentCrossResult } from "@/types/api";
import { rapResultadoHex, STATUS_HEX } from "@/lib/status-colors";
import type { ParsedRap } from "@/lib/grading";

/** Fila del listado de detalle: RAPs con problema/pendientes por aprendiz. */
export interface RapDetailEntry {
  name: string;
  issues: { rap: string; estado: string }[];
}

export interface RapHeatmapPdfParams {
  /** Número de ficha (para título y encabezados). */
  ficha?: string;
  /** Nombre del programa de formación. */
  courseName?: string;
  /** Etiqueta del filtro activo, p. ej. " (Con problemas)", o "" si es Todos. */
  filterLabel: string;
  /** Total de aprendices de la ficha (sin filtrar). */
  totalStudents: number;
  /** Aprendices que van al PDF (ya filtrados, ordenados y sin excluidos). */
  students: StudentCrossResult[];
  /** Nombres completos de los RAPs que van al PDF (sin excluidos). */
  rapNames: string[];
  /** RAPs parseados, en el mismo orden que rapNames. */
  rapParsed: ParsedRap[];
  /** Detalle por aprendiz (RAPs no correctos/listos) para la página 2. */
  detailByStudent: RapDetailEntry[];
  /** Incluir la página de detalle por aprendiz. */
  includeDetail: boolean;
}

/** Construye el HTML completo del PDF del heatmap de juicios evaluativos. */
export function buildRapHeatmapPdfHtml(params: RapHeatmapPdfParams): string {
  const {
    ficha,
    courseName,
    filterLabel,
    totalStudents,
    students: studentsForPDF,
    rapNames: pdfRapNames,
    rapParsed: pdfRapParsed,
    detailByStudent,
    includeDetail,
  } = params;

  const today = new Date().toLocaleDateString("es-CO", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const title = courseName
    ? `Juicios Evaluativos - Ficha ${ficha} - ${courseName}${filterLabel}`
    : `Juicios Evaluativos - Ficha ${ficha}${filterLabel}`;

  const cellSize = 15;
  const cellGap = 2;
  const nameWidth = 230;
  const headerHeight = 100;

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${title}</title>
  <style>
    @page { size: landscape; margin: 15mm 12mm; }

    * { box-sizing: border-box; }
    body {
      font-family: 'Work Sans', 'Calibri', 'Segoe UI', Arial, sans-serif;
      margin: 0;
      padding: 0;
      color: #1a1a1a;
    }

    /* Header */
    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
      padding-bottom: 10px;
      border-bottom: 2px solid #39A900;
    }
    .header h1 { font-size: 15px; font-weight: 700; color: #00324D; margin: 0 0 3px 0; }
    .header .subtitle { font-size: 10px; color: #6B6B6B; margin: 0; }
    .header .badge {
      background: #39A900; color: white; font-size: 9px; font-weight: 600;
      padding: 3px 10px; border-radius: 12px; white-space: nowrap;
    }

    .legend { display: flex; gap: 14px; margin-bottom: 10px; font-size: 9px; color: #4A4A4A; flex-wrap: wrap; }
    .legend-item { display: flex; align-items: center; gap: 4px; }
    .legend-box { width: 12px; height: 12px; border-radius: 3px; }

    /* Heatmap table */
    table.heatmap { border-collapse: separate; border-spacing: ${cellGap}px; }
    table.heatmap th, table.heatmap td { padding: 0; }
    table.heatmap th.rap-header {
      width: ${cellSize}px;
      height: ${headerHeight}px;
      position: relative;
      vertical-align: bottom;
    }
    table.heatmap th.rap-header > div {
      writing-mode: vertical-lr;
      transform: rotate(180deg);
      font-size: 8px;
      font-weight: 500;
      color: #6B6B6B;
      white-space: nowrap;
      overflow: hidden;
      max-height: ${headerHeight - 6}px;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      width: 100%;
      padding: 2px 0;
    }
    table.heatmap td.name-cell {
      width: ${nameWidth}px; max-width: ${nameWidth}px;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      padding-right: 6px; font-size: 8px; font-weight: 500; color: #1A1A1A;
    }
    table.heatmap td.grade-cell {
      width: ${cellSize}px; height: ${cellSize}px; min-width: ${cellSize}px; border-radius: 3px;
    }
    .heatmap-footer { margin-top: 8px; font-size: 9px; color: #6B6B6B; text-align: right; }

    /* Detail page */
    .detail-page { page-break-before: always; padding: 0; }
    .detail-page h2 { font-size: 14px; font-weight: 700; color: #00324D; margin: 0 0 4px 0; }
    .detail-list { columns: 2; column-gap: 24px; font-size: 9px; }
    .detail-item {
      break-inside: avoid; margin-bottom: 10px; padding: 6px 8px;
      background: #F8F8F6; border-radius: 6px; border: 1px solid #E2E2DD;
    }
    .detail-item .student-name { font-weight: 600; font-size: 9px; color: #1A1A1A; margin-bottom: 2px; }
    .detail-item .count-badge {
      display: inline-block; background: #39A900; color: white;
      font-size: 7px; font-weight: 600; padding: 1px 5px; border-radius: 8px; margin-left: 4px;
    }
    .detail-codes { color: #6B6B6B; font-size: 8px; line-height: 1.4; }

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
        <p class="subtitle">Fecha: ${today} | ${studentsForPDF.length} de ${totalStudents} aprendices x ${pdfRapNames.length} RAPs</p>
      </div>
      <div class="badge">ZAJUNA MONITOR</div>
    </div>

    <div class="legend">
      <div class="legend-item"><div class="legend-box" style="background:${rapResultadoHex("listo_para_aprobar")}"></div> Listo para Aprobar</div>
      <div class="legend-item"><div class="legend-box" style="background:${rapResultadoHex("correcto")}"></div> Correcto</div>
      <div class="legend-item"><div class="legend-box" style="background:${rapResultadoHex("pendiente")}"></div> Pendiente</div>
      <div class="legend-item"><div class="legend-box" style="background:${rapResultadoHex("con_problemas")}"></div> Con Problemas</div>
      <div class="legend-item"><div class="legend-box" style="background:${rapResultadoHex("inconsistencia")}"></div> Inconsistencia</div>
      <div class="legend-item"><div class="legend-box" style="background:${rapResultadoHex("aprobado_anticipado")}"></div> Aprobado Anticipado</div>
    </div>

    <table class="heatmap">
      <thead>
        <tr>
          <th style="width:${nameWidth}px"></th>
          ${pdfRapParsed.map((parsed) => `<th class="rap-header"><div>${parsed.code}-${parsed.number}</div></th>`).join("")}
        </tr>
      </thead>
      <tbody>
        ${studentsForPDF
          .map((student) => {
            const rapLookup = new Map(student.raps.map((r) => [r.rap, r]));
            const cells = pdfRapNames
              .map((rap) => {
                const result = rapLookup.get(rap);
                const hex = result ? rapResultadoHex(result.resultado) : STATUS_HEX.pending.soft;
                return '<td class="grade-cell" style="background-color:' + hex + ' !important"></td>';
              })
              .join("");
            return '<tr><td class="name-cell">' + student.full_name + '</td>' + cells + '</tr>';
          })
          .join("")}
      </tbody>
    </table>
    <div class="heatmap-footer">Generado por Zajuna Monitor</div>
  </div>

  ${includeDetail ? `<!-- PAGE 2+: Detail (Letter Portrait) -->
  <div class="detail-page">
    <div class="header">
      <div>
        <h2>RAPs Pendientes / Con Problemas por Aprendiz</h2>
        <p class="subtitle">Ficha ${ficha}${filterLabel} | ${today}</p>
      </div>
      <div class="badge">ZAJUNA MONITOR</div>
    </div>
    <div class="detail-list">
      ${detailByStudent
        .filter((s) => s.issues.length > 0)
        .map(
          (s) => '<div class="detail-item">' +
            '<div class="student-name">' + s.name + '<span class="count-badge">' + s.issues.length + '</span></div>' +
            '<div class="detail-codes">' + s.issues.map((i) => i.rap + ' (' + i.estado + ')').join(", ") + '</div>' +
          '</div>'
        )
        .join("")}
    </div>
  </div>` : ""}
</body>
</html>`;
}
