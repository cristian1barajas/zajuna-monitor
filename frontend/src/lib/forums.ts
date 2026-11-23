import type { ForumContribution, ForumContributionStatus } from "@/types/api";

/** Estados que todavía piden réplica del instructor. */
export const NEEDS_REPLY: ReadonlySet<ForumContributionStatus> = new Set(["vencido", "vence_hoy", "a_tiempo"]);

export function needsReply(c: ForumContribution): boolean {
  return NEEDS_REPLY.has(c.status);
}

const URGENCY: Record<ForumContributionStatus, number> = {
  vencido: 0,
  vence_hoy: 1,
  a_tiempo: 2,
  respondido_tarde: 3,
  respondido: 4,
};

/** Lo urgente arriba y, dentro de cada estado, lo que lleva más tiempo esperando. */
export function sortByUrgency(items: ForumContribution[]): ForumContribution[] {
  return [...items].sort(
    (a, b) => URGENCY[a.status] - URGENCY[b.status] || (a.created_at ?? "").localeCompare(b.created_at ?? ""),
  );
}

/** "2026-11-03" → mar 3 nov (fecha local, sin corrimiento por zona horaria). */
export function formatDay(isoDay: string): string {
  const [y, m, d] = isoDay.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "short" });
}

/** Fecha y hora de una publicación en hora de Colombia. */
export function formatPostTime(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    timeZone: "America/Bogota",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** El error de la petición, en palabras del instructor. */
export function describeForumError(e: unknown): string {
  const message = e instanceof Error ? e.message : "";
  if (message === "Failed to fetch" || message.includes("NetworkError")) {
    return "Se cortó la conexión con el monitor mientras revisaba el foro. Vuelve a intentarlo.";
  }
  if (message.includes("API error 409")) {
    return "Falta conectar tu cuenta de Zajuna en tu perfil o sincronizar el grupo antes de revisar foros.";
  }
  if (message.includes("API error 503")) {
    return "Zajuna no dejó iniciar sesión en este momento. Suele pasar por ratos: reintenta en un minuto.";
  }
  if (message.includes("API error 502")) {
    return "Zajuna no respondió al abrir el foro. Reintenta en un momento.";
  }
  return message || "Error desconocido";
}
