/**
 * Lógica de dominio de "Por Calificar": filtros por guía, fase, tipo y
 * cierre, y qué cuenta como pendiente. Sin React, para poder probarla.
 */
import type {
  CronogramaResponse,
  EvidenceItem,
  PendingGradingResult,
} from "@/types/api";

export type EvidenceKind = "assign" | "forum" | "quiz";
export type ClosingBucket = "vencida" | "semana" | "despues" | "sin-fecha";

export const KIND_LABELS: Record<EvidenceKind, string> = {
  assign: "Tareas",
  forum: "Foros",
  quiz: "Cuestionarios",
};

export const CLOSING_LABELS: Record<ClosingBucket, string> = {
  vencida: "Ya cerró",
  semana: "Cierra esta semana",
  despues: "Cierra después",
  "sin-fecha": "Sin fecha",
};

export interface PendingFilters {
  text: string;
  guides: Set<string>;
  phases: Set<string>;
  kinds: Set<EvidenceKind>;
  closing: Set<ClosingBucket>;
}

export const EMPTY_FILTERS: PendingFilters = {
  text: "",
  guides: new Set(),
  phases: new Set(),
  kinds: new Set(),
  closing: new Set(),
};

/** "Cuestionario. GA3-240202501-AA2-EV01." → "GA3"; sin código GA → null. */
export function guideOf(name: string): string | null {
  const match = name.match(/\b(GA\d+)-\d+-AA\d+-EV\d+/i);
  return match ? match[1].toUpperCase() : null;
}

/** Orden natural de guías: GA2 antes que GA10. */
export function compareGuides(a: string, b: string): number {
  return Number(a.slice(2)) - Number(b.slice(2));
}

export function kindOf(
  itemId: number,
  moduleTypes: Map<number, string>,
): EvidenceKind {
  const type = moduleTypes.get(itemId);
  return type === "forum" || type === "quiz" ? type : "assign";
}

/** item_id → fecha de cierre (YYYY-MM-DD) según el cronograma cargado. */
export function buildCutoffMap(
  cronograma: CronogramaResponse | null,
): Map<number, string> {
  const map = new Map<number, string>();
  for (const entry of cronograma?.entries ?? []) {
    if (entry.evidence_item_id != null) {
      map.set(entry.evidence_item_id, entry.cutoff_date);
    }
  }
  return map;
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** Ubica una fecha de cierre respecto a hoy: vencida, en 7 días o después. */
export function closingBucket(
  cutoff: string | undefined,
  today: Date = new Date(),
): ClosingBucket {
  if (!cutoff) return "sin-fecha";
  const [y, m, d] = cutoff.split("-").map(Number);
  if (!y || !m || !d) return "sin-fecha";
  const days = (startOfDay(new Date(y, m - 1, d)) - startOfDay(today)) / 86_400_000;
  if (days < 0) return "vencida";
  if (days <= 7) return "semana";
  return "despues";
}

export function applyFilters(
  evidences: EvidenceItem[],
  filters: PendingFilters,
  moduleTypes: Map<number, string>,
  cutoffs: Map<number, string>,
  today: Date = new Date(),
): EvidenceItem[] {
  const text = filters.text.trim().toLowerCase();
  return evidences.filter((ev) => {
    if (text && !ev.name.toLowerCase().includes(text)) return false;
    if (filters.guides.size > 0) {
      const guide = guideOf(ev.name);
      if (!guide || !filters.guides.has(guide)) return false;
    }
    if (filters.phases.size > 0 && !filters.phases.has(ev.category)) return false;
    if (filters.kinds.size > 0 && !filters.kinds.has(kindOf(ev.item_id, moduleTypes))) {
      return false;
    }
    if (
      filters.closing.size > 0 &&
      !filters.closing.has(closingBucket(cutoffs.get(ev.item_id), today))
    ) {
      return false;
    }
    return true;
  });
}

interface StoredFilters {
  text: string;
  guides: string[];
  phases: string[];
  kinds: EvidenceKind[];
  closing: ClosingBucket[];
}

export function serializeFilters(filters: PendingFilters): string {
  const stored: StoredFilters = {
    text: filters.text,
    guides: [...filters.guides],
    phases: [...filters.phases],
    kinds: [...filters.kinds],
    closing: [...filters.closing],
  };
  return JSON.stringify(stored);
}

export function parseFilters(raw: string | null): PendingFilters {
  if (!raw) return EMPTY_FILTERS;
  try {
    const s = JSON.parse(raw) as Partial<StoredFilters>;
    return {
      text: s.text ?? "",
      guides: new Set(s.guides ?? []),
      phases: new Set(s.phases ?? []),
      kinds: new Set(s.kinds ?? []),
      closing: new Set(s.closing ?? []),
    };
  } catch {
    return EMPTY_FILTERS;
  }
}

export function hasActiveFilters(filters: PendingFilters): boolean {
  return (
    filters.text.trim() !== "" ||
    filters.guides.size > 0 ||
    filters.phases.size > 0 ||
    filters.kinds.size > 0 ||
    filters.closing.size > 0
  );
}

/** Clave de la última consulta de Por Calificar de una ficha (localStorage). */
export function resultsStorageKey(ficha: string): string {
  return `pending-grading-results-${ficha}`;
}

/** Evento que avisa en esta pestaña que cambió una consulta guardada. */
export const RESULTS_UPDATED_EVENT = "pending-grading-results-updated";

/**
 * Entregas por calificar según la última consulta guardada de la ficha;
 * null si nunca se consultó. Lo usa la barra lateral para el contador.
 */
export function storedToGrade(ficha: string): number | null {
  try {
    const raw = localStorage.getItem(resultsStorageKey(ficha));
    if (!raw) return null;
    const stored = JSON.parse(raw) as { results?: PendingGradingResult[] };
    return (stored.results ?? [])
      .filter(needsAction)
      .reduce((sum, r) => sum + (r.needs_grading ?? 0), 0);
  } catch {
    return null;
  }
}

/** Un resultado pide acción del instructor si hay algo sin calificar. */
export function needsAction(result: PendingGradingResult | undefined): boolean {
  if (!result || result.error) return false;
  if (result.module_type === "quiz") return false;
  return (result.needs_grading ?? 0) > 0;
}

/** Tareas con entregas por calificar: son las que se pueden descargar. */
export function downloadableResults(
  results: Iterable<PendingGradingResult>,
): PendingGradingResult[] {
  return [...results].filter(
    (r) => r.module_type === "assign" && r.cmid != null && needsAction(r),
  );
}
