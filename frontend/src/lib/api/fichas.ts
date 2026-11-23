import type {
  HealthResponse,
  DashboardResponse,
  FichaSummaryItem,
  FichaDetailResponse,
  PendingSubmissionsResponse,
  AlertsResponse,
  ActivitySummaryItem,
  ActivityResponse,
} from "@/types/api";

import { apiFetch, apiFetchCached, clearReadCache } from "./core";

/** Evento que avisa en esta pestaña que cambiaron los grupos que se ven. */
export const FICHAS_CHANGED_EVENT = "zajuna-fichas-changed";

/** Tras agregar o quitar grupos: descarta lo leído y avisa a la barra lateral. */
export function notifyFichasChanged(): void {
  clearReadCache();
  window.dispatchEvent(new Event(FICHAS_CHANGED_EVENT));
}

export function fetchHealth() {
  return apiFetch<HealthResponse>("/api/health");
}

export function fetchDashboard() {
  return apiFetchCached<DashboardResponse>("/api/dashboard");
}

export function fetchFichas() {
  return apiFetchCached<FichaSummaryItem[]>("/api/fichas");
}

export function fetchFichaDetail(ficha: string) {
  return apiFetchCached<FichaDetailResponse>(`/api/fichas/${ficha}`);
}

export function fetchPendingSubmissions(ficha: string) {
  return apiFetchCached<PendingSubmissionsResponse>(`/api/fichas/${ficha}/pendientes`);
}

export function fetchAlerts(ficha?: string, severity?: string) {
  const params = new URLSearchParams();
  if (ficha) params.set("ficha", ficha);
  if (severity) params.set("severity", severity);
  const qs = params.toString();
  return apiFetchCached<AlertsResponse>(`/api/alerts${qs ? `?${qs}` : ""}`);
}

export function fetchActivitySummary() {
  return apiFetchCached<ActivitySummaryItem[]>("/api/activity");
}

export function fetchActivity(ficha: string, minDaysInactive?: number) {
  const params = new URLSearchParams();
  if (minDaysInactive !== undefined) params.set("min_days_inactive", String(minDaysInactive));
  const qs = params.toString();
  return apiFetchCached<ActivityResponse>(`/api/activity/${ficha}${qs ? `?${qs}` : ""}`);
}
