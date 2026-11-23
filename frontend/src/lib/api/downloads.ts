import { apiFetch, apiPost } from "./core";

// --- Download Evidences ---

export function fetchSubmissions(ficha: string, cmid: number) {
  return apiFetch<import("@/types/api").SubmissionsListResponse>(
    `/api/fichas/${ficha}/submissions/${cmid}`,
  );
}

export function startEvidenceDownload(
  ficha: string,
  body: {
    cmid: number;
    target_dir: string;
    include_instrument: boolean;
    status_filter: string[];
  },
) {
  return apiPost<{ job_id: string }>(
    `/api/fichas/${ficha}/download-evidence`,
    body,
  );
}

/** Descarga en un solo trabajo las entregas por calificar de varias tareas. */
export function startPendingDownload(
  ficha: string,
  body: { cmids: number[]; target_dir: string; include_instrument: boolean },
) {
  return apiPost<{ job_id: string }>(
    `/api/fichas/${ficha}/download-pending`,
    body,
  );
}

export function fetchPendingDownloadStatus(ficha: string, jobId: string) {
  return apiFetch<import("@/types/api").BatchDownloadStatusResponse>(
    `/api/fichas/${ficha}/download-pending-status/${jobId}`,
  );
}

export function fetchDownloadStatus(ficha: string, jobId: string) {
  return apiFetch<import("@/types/api").DownloadStatusResponse>(
    `/api/fichas/${ficha}/download-status/${jobId}`,
  );
}
