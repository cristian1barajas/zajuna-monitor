/**
 * Generador del HTML de exportación PDF de "Asignar en Sofía": la lista de
 * aprendices para aprobar o la de no aprobar (un PDF por lista), por
 * competencia y RAP, con los códigos de Sofía Plus. Función pura: recibe los
 * datos y devuelve el HTML para imprimir.
 */

import type { AprendizPorAsignar, JuiciosPorAsignarResponse, RapPorAsignar } from "@/types/api";

export type JuiciosPdfLista = "aprobar" | "no_aprobar";

export interface JuiciosPorAsignarPdfParams {
  ficha: string;
  /** Nombre del programa de formación. */
  courseName?: string;
  data: JuiciosPorAsignarResponse;
  /** Lista que va al PDF. */
  lista: JuiciosPdfLista;
  /** Texto del corte de evidencias, p. ej. "Guías 1 a 4 · corte 30 oct". */
  corte: string;
  /** Marca de cada aprendiz: (lista, código del RAP, documento) → marcado. */
  isMarked: (lista: JuiciosPdfLista, rapCode: string, document: string) => boolean;
}

const LISTAS: Record<JuiciosPdfLista, { title: string; file: string; hint: string; color: string; soft: string }> = {
  aprobar: {
    title: "Aprobar en Sofía Plus",
    file: "Aprobar_Sofia",
    hint: "Todas las evidencias del RAP en A",
    color: "#2E7D32",
    soft: "#EAF4EA",
  },
  no_aprobar: {
    title: "No aprobar en Sofía Plus",
    file: "No_Aprobar_Sofia",
    hint: "Alguna evidencia con D o sin entregar hasta el corte",
    color: "#B3261E",
    soft: "#FBEAEA",
  },
};

function esc(text: string | number): string {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** RAPs agrupados por competencia, en el orden que llegan. */
function byCompetencia(raps: RapPorAsignar[]) {
  const groups: { first: RapPorAsignar; raps: RapPorAsignar[] }[] = [];
  for (const rap of raps) {
    const last = groups.at(-1);
    if (last && last.first.competencia_code === rap.competencia_code && last.first.competencia_programa === rap.competencia_programa) {
      last.raps.push(rap);
    } else {
      groups.push({ first: rap, raps: [rap] });
    }
  }
  return groups;
}

function detalle(lista: JuiciosPdfLista, a: AprendizPorAsignar): string {
  if (lista === "aprobar") return `${a.aprobadas}/${a.total} en A`;
  return [a.desaprobadas > 0 && `${a.desaprobadas} con D`, a.sin_entregar > 0 && `${a.sin_entregar} sin entregar`]
    .filter(Boolean)
    .join(" · ");
}

function rapTable(lista: JuiciosPdfLista, rap: RapPorAsignar, isMarked: JuiciosPorAsignarPdfParams["isMarked"]): string {
  const rows = rap.aprendices
    .map((a, i) => {
      const on = isMarked(lista, rap.rap_code, a.document);
      return `<tr>
        <td class="chk">${on ? "&#9745;" : "&#9744;"}</td>
        <td class="num">${i + 1}</td>
        <td class="name">${esc(a.full_name)}</td>
        <td class="doc">${esc(a.document)}</td>
        <td class="det">${esc(detalle(lista, a))}</td>
      </tr>`;
    })
    .join("");
  return `<div class="rap">
    <div class="rap-head">
      <span class="lbl">RAP</span> <span class="code">${esc(rap.rap_code)}</span>
      ${rap.rap_programa ? `<span class="meta">· ${esc(rap.rap_programa)}</span>` : ""}
      ${rap.fase ? `<span class="meta">· ${esc(rap.fase)}</span>` : ""}
      <span class="count">${rap.aprendices.length} ${rap.aprendices.length === 1 ? "aprendiz" : "aprendices"}</span>
      <div class="desc">${esc(rap.rap_desc)}</div>
    </div>
    <table>
      <thead><tr><th class="chk"></th><th class="num">#</th><th>Aprendiz</th><th class="doc">Documento</th><th class="det">Evidencias</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

function section(lista: JuiciosPdfLista, raps: RapPorAsignar[], isMarked: JuiciosPorAsignarPdfParams["isMarked"]): string {
  const cfg = LISTAS[lista];
  const total = raps.reduce((n, r) => n + r.aprendices.length, 0);
  const body =
    raps.length === 0
      ? `<p class="empty">No hay aprendices en esta lista con la selección de evidencias actual.</p>`
      : byCompetencia(raps)
          .map(
            (g) => `<div class="comp">
        <div class="comp-head">
          <span class="lbl">Competencia</span> <span class="code">${esc(g.first.competencia_code)}</span>
          ${g.first.competencia_programa ? `<span class="meta">· programa ${esc(g.first.competencia_programa)}</span>` : ""}
          <div class="desc">${esc(g.first.competencia_desc)}</div>
        </div>
        ${g.raps.map((rap) => rapTable(lista, rap, isMarked)).join("")}
      </div>`,
          )
          .join("");
  return `<section class="lista" style="--c:${cfg.color};--s:${cfg.soft}">
    <div class="lista-head">
      <div><h2>${cfg.title}</h2><p>${cfg.hint}</p></div>
      <div class="big">${total}<small>en ${raps.length} RAP</small></div>
    </div>
    ${body}
  </section>`;
}

/** Construye el HTML completo del PDF de juicios por asignar en Sofía. */
export function buildJuiciosPorAsignarPdfHtml(params: JuiciosPorAsignarPdfParams): string {
  const { ficha, courseName, data, lista, corte, isMarked } = params;
  const now = new Date();
  const today = now.toLocaleDateString("es-CO", { year: "numeric", month: "long", day: "numeric" });
  const title = `${LISTAS[lista].title} - Grupo ${ficha}`;
  // El título del documento es el nombre que propone "Guardar como PDF".
  const pad = (n: number) => String(n).padStart(2, "0");
  const fileName = `${LISTAS[lista].file}_${ficha}_${pad(now.getDate())}-${pad(now.getMonth() + 1)}-${pad(now.getFullYear() % 100)}`;
  const excluidos = [
    data.con_novedad > 0 && `${data.con_novedad} con novedad`,
    data.suspendidos > 0 && `${data.suspendidos} suspendidos en Zajuna`,
    data.fuera_de_formacion > 0 && `${data.fuera_de_formacion} que no están EN FORMACIÓN en Sofía`,
  ].filter(Boolean);

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${esc(fileName)}</title>
  <style>
    @page { size: letter portrait; margin: 14mm 12mm; }
    * { box-sizing: border-box; }
    body { font-family: 'Work Sans', 'Calibri', 'Segoe UI', Arial, sans-serif; margin: 0; color: #1a1a1a; font-size: 10px;
      -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;
      padding-bottom: 8px; margin-bottom: 8px; border-bottom: 2px solid #39A900; }
    .header h1 { font-size: 15px; font-weight: 700; color: #00324D; margin: 0 0 3px; }
    .header p { font-size: 10px; color: #6B6B6B; margin: 1px 0; }
    .badge { background: #39A900; color: #fff; font-size: 9px; font-weight: 600; padding: 3px 10px; border-radius: 12px; white-space: nowrap; }
    .note { font-size: 9px; color: #6B6B6B; margin: 0 0 10px; }

    .lista-head { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; margin-bottom: 10px;
      border: 1px solid var(--c); border-left-width: 5px; border-radius: 6px; background: var(--s); }
    .lista-head h2 { margin: 0; font-size: 13px; color: var(--c); }
    .lista-head p { margin: 2px 0 0; font-size: 9px; color: #4A4A4A; }
    .big { font-size: 22px; font-weight: 700; color: var(--c); text-align: right; line-height: 1; }
    .big small { display: block; font-size: 8px; font-weight: 500; color: #6B6B6B; margin-top: 2px; }
    .empty { padding: 16px; text-align: center; color: #6B6B6B; border: 1px dashed #ccc; border-radius: 6px; }

    .comp { margin-bottom: 12px; }
    .comp-head { padding: 5px 10px; border-left: 4px solid #00324D; background: #F3F5F7; border-radius: 4px; margin-bottom: 6px;
      break-after: avoid; page-break-after: avoid; }
    .lbl { font-size: 8px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: #6B6B6B; }
    .code { font-family: Consolas, 'Courier New', monospace; font-weight: 700; font-size: 10px; }
    .meta { font-size: 9px; color: #6B6B6B; }
    .desc { font-size: 10px; font-weight: 600; margin-top: 2px; line-height: 1.3; }

    .rap { margin: 0 0 8px 10px; border: 1px solid #E2E2DD; border-radius: 5px; overflow: hidden; break-inside: avoid; page-break-inside: avoid; }
    .rap-head { padding: 4px 8px; background: #FAFAF8; border-bottom: 1px solid #E2E2DD; }
    .rap-head .desc { font-weight: 500; }
    .count { float: right; font-size: 9px; color: #6B6B6B; }
    table { width: 100%; border-collapse: collapse; }
    th { font-size: 8px; font-weight: 600; color: #6B6B6B; text-align: left; padding: 3px 6px; border-bottom: 1px solid #E2E2DD; }
    td { padding: 3px 6px; border-bottom: 1px solid #F0F0EC; font-size: 9.5px; }
    tr:last-child td { border-bottom: 0; }
    .chk { width: 18px; font-size: 12px; text-align: center; }
    .num { width: 22px; text-align: right; color: #6B6B6B; }
    .name { font-weight: 500; }
    .doc { width: 90px; font-family: Consolas, 'Courier New', monospace; color: #4A4A4A; }
    .det { width: 140px; color: #4A4A4A; }
    .footer { margin-top: 10px; font-size: 8px; color: #6B6B6B; text-align: right; }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>${esc(title)}</h1>
      ${courseName ? `<p>${esc(courseName)}</p>` : ""}
      <p>Fecha: ${today} | Evidencias: ${esc(corte)}</p>
    </div>
    <div class="badge">ZAJUNA MONITOR</div>
  </div>
  ${excluidos.length ? `<p class="note">No se listan: ${esc(excluidos.join(" · "))}.</p>` : ""}
  ${section(lista, data[lista], isMarked)}
  <div class="footer">Generado por Zajuna Monitor</div>
</body>
</html>`;
}
