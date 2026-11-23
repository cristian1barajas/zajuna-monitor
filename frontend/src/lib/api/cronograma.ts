import type { CronogramaPdfPreview, CronogramaResponse } from "@/types/api";

import { authedFetch, apiFetch, apiPost, apiDelete } from "./core";

export function fetchCronograma(ficha: string) {
  return apiFetch<CronogramaResponse>(`/api/cronograma/${ficha}`);
}

export function postCronograma(
  ficha: string,
  entries: { evidence_name: string; cutoff_date: string }[],
) {
  return apiPost<CronogramaResponse>(`/api/cronograma/${ficha}`, {
    ficha,
    entries,
  });
}

/** Lee los PDF del cronograma (uno por mes) sin guardar nada. */
export async function previewCronogramaPdfs(
  ficha: string,
  files: File[],
): Promise<CronogramaPdfPreview> {
  const formData = new FormData();
  for (const file of files) formData.append("files", file);
  const res = await authedFetch(`/api/cronograma/${ficha}/pdf`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    // El backend explica qué falló en cada archivo
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export function deleteCronograma(ficha: string) {
  return apiDelete<{ deleted: boolean }>(`/api/cronograma/${ficha}`);
}
