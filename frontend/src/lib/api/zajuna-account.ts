import { apiFetch, apiPost, apiDelete } from "./core";

// --- Cuenta Zajuna (credenciales de scraping por instructor) ---

export interface ZajunaAccountStatus {
  connected: boolean;
  type_document?: string | null;
  document_masked?: string | null;
  status?: string | null;
  connected_at?: string | null;
  last_validated_at?: string | null;
}

export function fetchZajunaAccount() {
  return apiFetch<ZajunaAccountStatus>("/api/zajuna-account");
}

export function connectZajunaAccount(payload: {
  type_document: string;
  document: string;
  password: string;
}) {
  return apiPost<ZajunaAccountStatus>("/api/zajuna-account", payload);
}

export async function disconnectZajunaAccount(): Promise<ZajunaAccountStatus> {
  return apiDelete<ZajunaAccountStatus>("/api/zajuna-account");
}
