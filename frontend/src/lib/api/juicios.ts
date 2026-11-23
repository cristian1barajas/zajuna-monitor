import type {
  RapMappingInput,
  RapMappingResponse,
  SofiaReportInput,
  SofiaReportResponse,
  RapCrossResponse,
  JuiciosPorAsignarResponse,
} from "@/types/api";

import { apiFetch, apiPost, apiDelete } from "./core";

// --- Juicios (RAP Cross-Reference) ---

export function fetchRapMapping(ficha: string) {
  return apiFetch<RapMappingResponse>(`/api/fichas/${ficha}/rap-mapping`);
}

export function postRapMapping(ficha: string, data: RapMappingInput) {
  return apiPost<RapMappingResponse>(`/api/fichas/${ficha}/rap-mapping`, data);
}

export function deleteRapMapping(ficha: string) {
  return apiDelete<{ deleted: boolean }>(`/api/fichas/${ficha}/rap-mapping`);
}

export function fetchSofiaReport(ficha: string) {
  return apiFetch<SofiaReportResponse>(`/api/fichas/${ficha}/sofia-report`);
}

export function postSofiaReport(ficha: string, data: SofiaReportInput) {
  return apiPost<SofiaReportResponse>(`/api/fichas/${ficha}/sofia-report`, data);
}

export function deleteSofiaReport(ficha: string) {
  return apiDelete<{ deleted: boolean }>(`/api/fichas/${ficha}/sofia-report`);
}

export function fetchRapCross(
  ficha: string,
  resultado?: string,
  document?: string,
) {
  const params = new URLSearchParams();
  if (resultado) params.set("resultado", resultado);
  if (document) params.set("document", document);
  const qs = params.toString();
  return apiFetch<RapCrossResponse>(
    `/api/fichas/${ficha}/rap-cross${qs ? `?${qs}` : ""}`,
  );
}

/** Aprendices a aprobar y a no aprobar en Sofía, por RAP, con las evidencias elegidas hasta el corte. */
export function postJuiciosPorAsignar(ficha: string, evidenceIds: number[]) {
  return apiPost<JuiciosPorAsignarResponse>(`/api/fichas/${ficha}/juicios-por-asignar`, {
    evidence_ids: evidenceIds,
  });
}
