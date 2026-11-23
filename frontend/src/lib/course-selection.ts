import type { ZajunaCourse } from "@/lib/api";

/** Fila del selector: un curso de Zajuna o uno seguido que ya no aparece allí. */
export interface CourseRow extends ZajunaCourse {
  /** Seguido en el registro pero ausente de "Mis cursos" (terminó o perdiste acceso). */
  missing: boolean;
}

/**
 * Une lo descubierto en Zajuna con lo que el instructor ya sigue.
 *
 * Selección inicial:
 * - Con registro guardado: los cursos seguidos.
 * - Sin registro (modo legado): las fichas que ya están en el monitor,
 *   para que guardar por primera vez no deje de sincronizar ninguna.
 */
export function buildCourseRows(
  discovered: ZajunaCourse[],
  tracked: ZajunaCourse[],
  configured: boolean,
  monitoredFichas: string[]
): { rows: CourseRow[]; selected: Set<number> } {
  const discoveredIds = new Set(discovered.map((c) => c.course_id));
  const trackedIds = new Set(tracked.map((c) => c.course_id));

  const rows: CourseRow[] = [
    ...discovered.map((c) => ({ ...c, tracked: trackedIds.has(c.course_id), missing: false })),
    ...tracked
      .filter((c) => !discoveredIds.has(c.course_id))
      .map((c) => ({ ...c, tracked: true, missing: true })),
  ].sort((a, b) => b.ficha.localeCompare(a.ficha));

  const monitored = new Set(monitoredFichas);
  const selected = new Set(
    rows
      .filter((r) => r.ficha && (configured ? r.tracked : monitored.has(r.ficha)))
      .map((r) => r.course_id)
  );
  return { rows, selected };
}

function matchesQuery(row: CourseRow, query: string): boolean {
  if (!query) return true;
  return [row.ficha, row.fullname, row.shortname, row.program_label]
    .some((text) => text.toLowerCase().includes(query));
}

/**
 * Reparte las filas para el selector según lo guardado (no lo marcado,
 * así una fila no salta de lista al marcarla): monitoreados, disponibles
 * con ficha y cursos sin ficha, que no se pueden monitorear.
 */
export function groupCourseRows(
  rows: CourseRow[],
  query: string
): { monitored: CourseRow[]; available: CourseRow[]; withoutFicha: CourseRow[] } {
  const q = query.trim().toLowerCase();
  const visible = rows.filter((r) => matchesQuery(r, q));
  return {
    monitored: visible.filter((r) => r.tracked),
    available: visible.filter((r) => !r.tracked && r.ficha),
    withoutFicha: visible.filter((r) => !r.tracked && !r.ficha),
  };
}
