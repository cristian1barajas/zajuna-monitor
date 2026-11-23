import type { DueProcessRecord } from "@/types/api";

/**
 * Etapas que reconoce la API en el asunto, en el orden de las carpetas del ZIP.
 * `tone` y `dot` repiten los colores de las cifras de Debido proceso.
 */
export const SOPORTE_STAGES = [
  {
    key: "primer_llamado",
    label: "Primer llamado",
    short: "1er llamado",
    tone: "text-warn-fg",
    dot: "bg-warn",
  },
  {
    key: "segundo_llamado",
    label: "Segundo llamado",
    short: "2do llamado",
    tone: "text-caution-fg",
    dot: "bg-caution",
  },
  {
    key: "tercer_llamado",
    label: "Tercer llamado",
    short: "3er llamado",
    tone: "text-caution-fg",
    dot: "bg-caution",
  },
  {
    key: "plan_mejoramiento",
    label: "Plan de mejoramiento",
    short: "Plan mejoramiento",
    tone: "text-danger-fg",
    dot: "bg-danger",
  },
  {
    key: "comite",
    label: "Comité de evaluación",
    short: "Comité",
    tone: "text-notice-fg",
    dot: "bg-notice",
  },
] as const;

export type SoporteStage = (typeof SOPORTE_STAGES)[number];

export function stageInfo(key: string): SoporteStage | undefined {
  return SOPORTE_STAGES.find((s) => s.key === key);
}

/** Nombre comparable entre el asunto del correo y el registro de la app. */
export function foldName(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}

export interface SendDate {
  date: string; // YYYY-MM-DD
  counts: { stage: string; count: number }[];
}

/** Fechas en que la app registró llamados (debido proceso), de la más reciente a la más antigua. */
export function sendDatesFromRecords(records: DueProcessRecord[]): SendDate[] {
  const byDate = new Map<string, Map<string, number>>();
  for (const r of records) {
    for (const h of r.history) {
      const day = h.date.slice(0, 10);
      const stages = byDate.get(day) ?? new Map<string, number>();
      stages.set(h.stage, (stages.get(h.stage) ?? 0) + 1);
      byDate.set(day, stages);
    }
  }
  const order = SOPORTE_STAGES.map((s) => s.key as string);
  return [...byDate.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([date, stages]) => ({
      date,
      counts: [...stages.entries()]
        .map(([stage, count]) => ({ stage, count }))
        .sort((a, b) => order.indexOf(a.stage) - order.indexOf(b.stage)),
    }));
}

function localDate(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** "2026-10-29" → "mié, 29 oct 2026" sin corrimiento por zona horaria. */
export function formatDay(day: string): string {
  return localDate(day).toLocaleDateString("es-CO", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** "2026-10-29" → { weekday: "jue", day: "29", month: "oct 2026" } para mostrarla compacta. */
export function dayParts(day: string): {
  weekday: string;
  day: string;
  month: string;
} {
  const date = localDate(day);
  return {
    weekday: date
      .toLocaleDateString("es-CO", { weekday: "short" })
      .replace(".", ""),
    day: String(date.getDate()),
    month: date
      .toLocaleDateString("es-CO", { month: "short", year: "numeric" })
      .replace(".", ""),
  };
}
