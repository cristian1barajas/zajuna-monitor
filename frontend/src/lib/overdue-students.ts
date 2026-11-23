/**
 * Lógica de dominio de la tabla de aprendices con evidencias vencidas
 * (filtrado, ordenamiento, conteos y selección). Pura y testeable sin React;
 * la UI vive en `components/reports/overdue-student-table.tsx`.
 */

import type { StudentReportItem } from "@/types/api";

export type SortField =
  | "full_name"
  | "overdue_count"
  | "last_access_days"
  | "status"
  | "document";
export type SortDir = "asc" | "desc";
/** Estado frente a las evidencias seleccionadas (control segmentado). */
export type FilterMode = "all" | "overdue" | "al_dia";
/** Subconjunto adicional (menú "Mostrar" y chips de alerta). */
export type StudentSubset =
  | "todos"
  | "sin_novedad"
  | "con_novedad"
  | "activos"
  | "suspendidos"
  | "inactivos"
  | "mitad";

export const SUBSET_LABELS: Record<StudentSubset, string> = {
  todos: "Todos los aprendices",
  activos: "Activos sin novedad",
  sin_novedad: "Sin novedad",
  con_novedad: "Con novedad",
  suspendidos: "Suspendidos",
  inactivos: "Más de 30 días sin conectarse",
  mitad: "Deben más de la mitad",
};

/** Debe más de la mitad de las evidencias seleccionadas en el reporte. */
export function owesOverHalf(student: StudentReportItem, selectedCount: number): boolean {
  return student.overdue_count > selectedCount * 0.5;
}

function inSubset(
  s: StudentReportItem,
  subset: StudentSubset,
  novedadIds: Set<number>,
  selectedCount: number,
): boolean {
  switch (subset) {
    case "sin_novedad":
      return !novedadIds.has(s.user_id);
    case "con_novedad":
      return novedadIds.has(s.user_id);
    case "activos":
      return s.status === "Activo" && !novedadIds.has(s.user_id);
    case "suspendidos":
      return s.status === "Suspendido";
    case "inactivos":
      return s.last_access_days >= 30;
    case "mitad":
      return owesOverHalf(s, selectedCount);
    default:
      return true;
  }
}

/** Filtra por búsqueda de texto (nombre, cédula, email), estado y subconjunto. */
export function filterStudents(
  students: StudentReportItem[],
  searchQuery: string,
  filterMode: FilterMode,
  novedadIds: Set<number>,
  subset: StudentSubset = "todos",
  selectedCount = 0,
): StudentReportItem[] {
  let list = [...students];

  // Text search
  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase().trim();
    list = list.filter(
      (s) =>
        s.full_name.toLowerCase().includes(q) ||
        s.document.includes(q) ||
        s.email.toLowerCase().includes(q),
    );
  }

  if (filterMode === "overdue") {
    list = list.filter((s) => s.overdue_count > 0);
  } else if (filterMode === "al_dia") {
    list = list.filter((s) => s.overdue_count === 0);
  }

  return list.filter((s) => inSubset(s, subset, novedadIds, selectedCount));
}

/** Ordena una copia de la lista por el campo y dirección indicados. */
export function sortStudents(
  students: StudentReportItem[],
  sortField: SortField,
  sortDir: SortDir,
): StudentReportItem[] {
  const list = [...students];
  list.sort((a, b) => {
    let cmp = 0;
    switch (sortField) {
      case "full_name":
        cmp = a.full_name.localeCompare(b.full_name);
        break;
      case "document":
        cmp = a.document.localeCompare(b.document);
        break;
      case "overdue_count":
        cmp = a.overdue_count - b.overdue_count;
        break;
      case "last_access_days":
        cmp = a.last_access_days - b.last_access_days;
        break;
      case "status":
        cmp = a.status.localeCompare(b.status);
        break;
    }
    return sortDir === "asc" ? cmp : -cmp;
  });
  return list;
}

/** Seleccionable = con pendientes, sin novedad y no suspendido. */
export function isSelectableStudent(
  student: StudentReportItem,
  novedadIds: Set<number>,
): boolean {
  return (
    student.overdue_count > 0 &&
    !novedadIds.has(student.user_id) &&
    student.status !== "Suspendido"
  );
}

export interface StudentCounts {
  overdueCount: number;
  alDiaCount: number;
  subsets: Record<StudentSubset, number>;
}

/** Conteos para el control segmentado y el menú "Mostrar". */
export function countStudents(
  students: StudentReportItem[],
  novedadIds: Set<number>,
  selectedCount = 0,
): StudentCounts {
  const subsets = Object.fromEntries(
    (Object.keys(SUBSET_LABELS) as StudentSubset[]).map((k) => [
      k,
      students.filter((s) => inSubset(s, k, novedadIds, selectedCount)).length,
    ]),
  ) as Record<StudentSubset, number>;
  return {
    overdueCount: students.filter((s) => s.overdue_count > 0).length,
    alDiaCount: students.filter((s) => s.overdue_count === 0).length,
    subsets,
  };
}
