/**
 * cmm-auth.ts — Servicio de autenticación contra la API del Sistema CMM.
 *
 * Adaptado de app/services/auth.ts del repo oficial sena-dev-2026-frontend.
 * Mantiene las mismas claves de localStorage (cmm_access_token / cmm_refresh_token)
 * para que el handoff SSO con el front oficial funcione sin traducción cuando
 * el portal único de login exista (Fase 2).
 */

import { cmmFetch } from "./cmm-api";

/* ============================================================
   Tipos (espejo de los schemas del backend CMM)
   ============================================================ */

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthUser {
  id: number;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  email_verified: boolean;
}

/** Roles del CMM con acceso al Zajuna Monitor. */
export const MONITOR_ROLES = ["instructor", "admin"] as const;

export function canAccessMonitor(role: string): boolean {
  return (MONITOR_ROLES as readonly string[]).includes(role);
}

/* ============================================================
   Llamadas a la API CMM
   ============================================================ */

export async function loginUser(credentials: LoginCredentials): Promise<TokenPair> {
  return cmmFetch<TokenPair>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export async function getMe(accessToken: string): Promise<AuthUser> {
  return cmmFetch<AuthUser>("/auth/me", { token: accessToken });
}

export async function refreshAccessToken(refreshToken: string): Promise<string> {
  const res = await cmmFetch<{ access_token: string }>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  return res.access_token;
}

export async function requestMagicLink(
  email: string,
  type: "FIRST_LOGIN" | "RESET_PASSWORD" = "RESET_PASSWORD"
): Promise<void> {
  await cmmFetch("/auth/magic-link/request", {
    method: "POST",
    body: JSON.stringify({ email, type }),
  });
}

/** Verifica el magic link y establece la contraseña. Devuelve tokens de sesión. */
export async function verifyMagicLink(
  token: string,
  newPassword: string
): Promise<TokenPair> {
  return cmmFetch<TokenPair>("/auth/magic-link/verify", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

export async function logoutUser(): Promise<void> {
  const accessToken = getAccessToken();
  const refreshToken = getRefreshToken();
  if (accessToken && refreshToken) {
    try {
      await cmmFetch("/auth/logout", {
        method: "POST",
        token: accessToken,
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      /* la sesión local se limpia igual */
    }
  }
  clearSession();
}

/* ============================================================
   Gestión de sesión (localStorage — solo cliente)
   Mismas claves que el front oficial CMM.
   ============================================================ */

const KEY_ACCESS = "cmm_access_token";
const KEY_REFRESH = "cmm_refresh_token";

export function saveSession(tokens: Pick<TokenPair, "access_token" | "refresh_token">): void {
  localStorage.setItem(KEY_ACCESS, tokens.access_token);
  localStorage.setItem(KEY_REFRESH, tokens.refresh_token);
}

export function clearSession(): void {
  localStorage.removeItem(KEY_ACCESS);
  localStorage.removeItem(KEY_REFRESH);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY_ACCESS);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY_REFRESH);
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}
