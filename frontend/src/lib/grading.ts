/**
 * Helpers de dominio para calificaciones y juicios evaluativos.
 * Lógica pura compartida por los heatmaps de fichas (evidencias)
 * y de juicios (RAPs).
 */

import type { StudentItem, StudentCrossResult } from "@/types/api";

/** Theme-aware cell color for on-screen rendering (flips in dark mode). */
export function gradeColor(value: string, isSubmitted = false): string {
  switch (value) {
    case "A":
      return "var(--status-ok)";
    case "D":
      return "var(--status-danger)";
    default:
      return isSubmitted ? "var(--status-warn)" : "var(--status-pending)";
  }
}

/** Returns true if evidence belongs to etapa lectiva (has GA code) */
export function isLectiva(name: string): boolean {
  return /GA\d+-\d+-AA\d+-EV\d+/.test(name);
}

/** Cuenta aprobadas/pendientes/desaprobadas de un aprendiz sobre un conjunto de evidencias. */
export function countGrades(student: StudentItem, evidenceIds: number[]) {
  let aprobadas = 0;
  let pendientes = 0;
  let desaprobadas = 0;
  for (const eid of evidenceIds) {
    const grade = student.grades[String(eid)];
    const value = grade?.value ?? "-";
    if (value === "A") aprobadas++;
    else if (value === "D") desaprobadas++;
    else pendientes++;
  }
  return { aprobadas, pendientes, desaprobadas };
}

/** Extract short GA code from evidence name, e.g. "GA1-220501092-AA1-EV01 ..." → "GA1-AA1-EV01" */
export function extractGACode(name: string): string {
  const match = name.match(/GA\d+-\d+-AA\d+-EV\d+/);
  if (match) return match[0];
  // Fallback: short name
  return name.length > 25 ? name.slice(0, 25) : name;
}

/** Partes de un RAP parseado desde su nombre completo. */
export interface ParsedRap {
  code: string;
  number: string;
  description: string;
}

/** Criterios de ordenamiento del heatmap de juicios (RAPs). */
export type SortOption =
  | "name_asc"
  | "name_desc"
  | "listos_desc"
  | "pendientes_desc"
  | "problemas_desc";

/** Filtros de aprendices del heatmap de juicios (RAPs). */
export type FilterOption =
  | "all"
  | "matricula_activa"
  | "matricula_cancelada"
  | "con_listos"
  | "con_problemas"
  | "con_inconsistencias"
  | "todo_pendiente";

/** Parse RAP string like "220501092-01 - INTERPRETAR..." into parts */
export function parseRap(rap: string): ParsedRap {
  // Format: "220501092-01 - INTERPRETAR la documentación..."
  // Also handles: "38392-01 - VERIFICAR..." (shorter codes)
  const match = rap.match(/^(\d+)-(\d+)\s*-\s*(.+)/);
  if (match) {
    return { code: match[1], number: match[2], description: match[3] };
  }
  // Fallback: try to find any number after dash
  const dashIdx = rap.indexOf("-");
  if (dashIdx !== -1) {
    const afterDash = rap.substring(dashIdx + 1).trim();
    const numMatch = afterDash.match(/^(\d+)/);
    if (numMatch) {
      return { code: rap.substring(0, dashIdx), number: numMatch[1], description: rap };
    }
  }
  return { code: "", number: rap.substring(0, 10), description: rap };
}

/** Ordena aprendices del cruce RAP según el criterio seleccionado. */
export function sortStudents(students: StudentCrossResult[], sortBy: SortOption): StudentCrossResult[] {
  const sorted = [...students];
  switch (sortBy) {
    case "name_asc":
      return sorted.sort((a, b) => a.full_name.localeCompare(b.full_name, "es"));
    case "name_desc":
      return sorted.sort((a, b) => b.full_name.localeCompare(a.full_name, "es"));
    case "listos_desc":
      return sorted.sort((a, b) => b.listos_para_aprobar - a.listos_para_aprobar);
    case "pendientes_desc":
      return sorted.sort((a, b) => b.pendientes - a.pendientes);
    case "problemas_desc":
      return sorted.sort((a, b) => b.con_problemas - a.con_problemas);
    default:
      return sorted;
  }
}

/** Filtra aprendices del cruce RAP según el filtro seleccionado. */
export function filterStudents(students: StudentCrossResult[], filterBy: FilterOption): StudentCrossResult[] {
  switch (filterBy) {
    case "matricula_activa":
      return students.filter((s) => s.status === "Activo");
    case "matricula_cancelada":
      return students.filter((s) => s.status === "Suspendido");
    case "con_listos":
      return students.filter((s) => s.listos_para_aprobar > 0);
    case "con_problemas":
      return students.filter((s) => s.con_problemas > 0);
    case "con_inconsistencias":
      return students.filter((s) => s.inconsistencias > 0);
    case "todo_pendiente":
      return students.filter((s) => s.pendientes === s.raps.length);
    default:
      return students;
  }
}
