import type { AlertItem } from "@/types/api";

/**
 * A dónde lleva una alerta: la bandeja del foro, Por calificar filtrado por la
 * evidencia, o el resumen de la ficha si la alerta es de toda la ficha.
 */
export function alertHref(alert: AlertItem): string {
  const base = `/fichas/${alert.ficha}`;
  if (alert.forum_id != null) return `${base}/foros?f=${alert.forum_id}`;
  if (alert.item_id != null && alert.evidence_name) {
    return `${base}/pendientes-calificar?q=${encodeURIComponent(alert.evidence_name)}`;
  }
  return base;
}
