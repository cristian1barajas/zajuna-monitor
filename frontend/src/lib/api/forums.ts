import type { ForumInboxResponse, ForumListResponse } from "@/types/api";

import { apiFetch, apiPost, clearReadCache } from "./core";

// --- Foros: réplicas pendientes (solo lectura en Zajuna) ---

export function fetchForums(ficha: string) {
  return apiFetch<ForumListResponse>(`/api/fichas/${ficha}/foros`);
}

/** Última revisión guardada del foro (404 si nunca se ha revisado). */
export function fetchForumInbox(ficha: string, forumId: number) {
  return apiFetch<ForumInboxResponse>(`/api/fichas/${ficha}/foros/${forumId}/participaciones`);
}

/** Lee el foro en Zajuna, guarda la revisión y la devuelve. */
export async function checkForum(ficha: string, forumId: number) {
  const result = await apiPost<ForumInboxResponse>(`/api/fichas/${ficha}/foros/${forumId}/revisar`, {});
  // Las alertas salen de esta revisión: que no se lean del caché
  clearReadCache();
  return result;
}
