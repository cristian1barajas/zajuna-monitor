import type {
  AssignmentMappingResponse,
  PendingGradingResponse,
} from "@/types/api";

import { apiFetch, apiPost } from "./core";

// --- Pending Grading (Assignments) ---

export function fetchAssignments(ficha: string) {
  return apiFetch<AssignmentMappingResponse>(
    `/api/fichas/${ficha}/assignments`,
  );
}

export function checkPendingGrading(ficha: string, itemIds: number[]) {
  return apiPost<PendingGradingResponse>(
    `/api/fichas/${ficha}/pending-grading`,
    { item_ids: itemIds },
  );
}

export function checkSubmissionStatus(ficha: string, itemIds: number[], force = false) {
  return apiPost<{ ficha: string; pending_cells: string[]; checked_count: number; checked_at: string; from_cache: boolean }>(
    `/api/fichas/${ficha}/submission-status`,
    { item_ids: itemIds, force },
  );
}
