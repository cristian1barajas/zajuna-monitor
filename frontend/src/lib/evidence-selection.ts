/**
 * Evidencias elegidas "hasta el corte", por ficha. Reportes y Juicios
 * comparten la misma selección: lo que se marca en uno vale en el otro.
 */

/** Misma clave que el selector anterior de Reportes: la selección guardada se conserva. */
const SELECTION_KEY = "zajuna_report_evidences_";

export function readEvidenceSelection(ficha: string): Set<number> {
  try {
    const raw = localStorage.getItem(SELECTION_KEY + ficha);
    return new Set(raw ? (JSON.parse(raw) as number[]) : []);
  } catch {
    return new Set();
  }
}

export function writeEvidenceSelection(ficha: string, ids: Set<number>): void {
  try {
    if (ids.size > 0) {
      localStorage.setItem(SELECTION_KEY + ficha, JSON.stringify([...ids]));
    } else {
      localStorage.removeItem(SELECTION_KEY + ficha);
    }
  } catch {
    /* sin almacenamiento local: la selección vive solo en esta visita */
  }
}
