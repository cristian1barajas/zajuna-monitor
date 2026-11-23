import {
  getAccessToken,
  getRefreshToken,
  refreshAccessToken,
  saveSession,
  clearSession,
} from "@/lib/cmm-auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Header Authorization con el token de la sesión CMM (si existe). */
function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Refresh compartido para no disparar N refreshes en paralelo. */
let refreshInFlight: Promise<string> | null = null;

async function tryRefreshSession(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  try {
    refreshInFlight ??= refreshAccessToken(refreshToken);
    const newAccess = await refreshInFlight;
    saveSession({ access_token: newAccess, refresh_token: refreshToken });
    return newAccess;
  } catch {
    return null;
  } finally {
    refreshInFlight = null;
  }
}

/**
 * fetch autenticado contra la API del monitor.
 * Si el access token expiró (401), intenta renovarlo con el refresh token
 * del CMM y reintenta una vez; si no se puede, limpia sesión y va al login.
 */
export async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const doFetch = () =>
    fetch(`${API_URL}${path}`, {
      ...init,
      headers: { ...(init.headers as Record<string, string>), ...authHeaders() },
    });

  let res = await doFetch();

  if (res.status === 401 && typeof window !== "undefined") {
    const renewed = await tryRefreshSession();
    if (renewed) {
      res = await doFetch();
    }
    if (res.status === 401) {
      clearSession();
      window.location.href = "/login";
    }
  }

  return res;
}

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await authedFetch(path, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

/* --- Caché de lecturas en memoria ---------------------------------
   Los datos solo cambian cuando corre el scraper, pero cada navegación
   re-descargaba y re-parseaba el JSON completo (el detalle de ficha pesa
   cientos de KB). Este caché por módulo hace la navegación entre páginas
   instantánea; se limpia al terminar una sincronización o al cerrar
   sesión, y expira solo a los 60s como red de seguridad. */

const readCache = new Map<string, { at: number; data: unknown }>();
const READ_CACHE_TTL_MS = 60_000;

export function clearReadCache(): void {
  readCache.clear();
}

export async function apiFetchCached<T>(path: string): Promise<T> {
  const hit = readCache.get(path);
  if (hit && Date.now() - hit.at < READ_CACHE_TTL_MS) {
    return hit.data as T;
  }
  const data = await apiFetch<T>(path);
  readCache.set(path, { at: Date.now(), data });
  return data;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await authedFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await authedFetch(path, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}
