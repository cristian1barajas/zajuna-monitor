import type {
  ReportResponse,
  DueProcessResponse,
  EmailDraft,
  EmailDraftsResponse,
  AdvanceResponse,
  EvidenceItem,
  ComplaintCandidatesResponse,
  NovedadesResponse,
} from "@/types/api";

import { authedFetch, apiFetch, apiPost } from "./core";

export function postReport(ficha: string, evidenceIds: number[]) {
  return apiPost<ReportResponse>(`/api/reports/${ficha}`, {
    evidence_ids: evidenceIds,
  });
}

export function fetchDueProcess(ficha: string) {
  return apiFetch<DueProcessResponse>(`/api/due-process/${ficha}`);
}

export function postEmailDrafts(
  ficha: string,
  userIds: number[],
  evidenceIds: number[],
) {
  return apiPost<EmailDraftsResponse>(
    `/api/due-process/${ficha}/email-drafts`,
    { user_ids: userIds, evidence_ids: evidenceIds },
  );
}

/** Nombre del archivo en `Content-Disposition: attachment; filename="..."`. */
function filenameFromDisposition(header: string | null): string | null {
  const match = header?.match(/filename="([^"]+)"/);
  return match ? match[1] : null;
}

/**
 * Borradores como archivos de correo para Outlook: uno → `.eml`;
 * varios o `asZip` → `.zip` con un `.eml` por aprendiz. El nombre lo decide la API.
 */
export async function downloadEmailDraftsEml(
  ficha: string,
  drafts: EmailDraft[],
  asZip = false,
): Promise<{ blob: Blob; filename: string }> {
  const res = await authedFetch(`/api/due-process/${ficha}/email-drafts/eml`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      drafts: drafts.map((d) => ({
        user_id: d.user_id,
        full_name: d.full_name,
        email: d.email,
        subject: d.subject,
        body: d.body,
        stage: d.stage,
      })),
      as_zip: asZip,
    }),
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  const fallback =
    drafts.length === 1 && !asZip
      ? "correo-llamado.eml"
      : `correos-llamados-ficha-${ficha}-${new Date().toISOString().slice(0, 10)}.zip`;
  return {
    blob: await res.blob(),
    filename: filenameFromDisposition(res.headers.get("Content-Disposition")) ?? fallback,
  };
}

export function postAdvanceDueProcess(
  ficha: string,
  userIds: number[],
  evidenceIds: number[],
) {
  return apiPost<AdvanceResponse>(`/api/due-process/${ficha}/advance`, {
    user_ids: userIds,
    evidence_ids: evidenceIds,
  });
}

// --- Complaint Reports (Informes de Queja) ---

export function fetchComplaintEvidences(ficha: string) {
  return apiFetch<EvidenceItem[]>(
    `/api/fichas/${ficha}/complaint-evidences`,
  );
}

export function fetchComplaintCandidates(
  ficha: string,
  evidenceIds: number[],
  minDaysInactive: number = 20,
) {
  return apiPost<ComplaintCandidatesResponse>(
    `/api/fichas/${ficha}/complaint-candidates`,
    { evidence_ids: evidenceIds, min_days_inactive: minDaysInactive },
  );
}

export async function generateComplaintReports(
  ficha: string,
  userIds: number[],
  evidenceIds: number[],
  coordinatorName: string,
  instructorName: string,
  reportDate: string = "",
): Promise<Blob> {
  const res = await authedFetch(`/api/fichas/${ficha}/complaint-reports/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_ids: userIds,
      evidence_ids: evidenceIds,
      coordinator_name: coordinatorName,
      instructor_name: instructorName,
      report_date: reportDate,
    }),
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.blob();
}

export async function importPhoneData(
  folderPath: string,
): Promise<{ imported: Record<string, number> }> {
  return apiPost<{ imported: Record<string, number> }>(
    "/api/fichas/phone-data/import",
    { folder_path: folderPath },
  );
}

export async function uploadParticipantScreenshot(
  ficha: string,
  file: File,
): Promise<{ ficha: string; size: number; filename: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await authedFetch(
    `/api/fichas/${ficha}/participant-screenshot`,
    { method: "POST", body: formData },
  );
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export async function deleteParticipantScreenshot(
  ficha: string,
): Promise<void> {
  await authedFetch(`/api/fichas/${ficha}/participant-screenshot`, {
    method: "DELETE",
  });
}

// --- Novedades ---

export function fetchNovedades(ficha: string) {
  return apiFetch<NovedadesResponse>(`/api/fichas/${ficha}/novedades`);
}

export function postNovedades(
  ficha: string,
  userIds: number[],
  type: string = "cancelacion",
  note: string = "",
) {
  return apiPost<NovedadesResponse>(`/api/fichas/${ficha}/novedades`, {
    user_ids: userIds,
    type,
    note,
  });
}

export function removeNovedades(ficha: string, userIds: number[]) {
  return apiPost<NovedadesResponse>(`/api/fichas/${ficha}/novedades/remove`, {
    user_ids: userIds,
  });
}
