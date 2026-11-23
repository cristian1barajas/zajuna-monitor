/**
 * cmm-api.ts — Cliente HTTP para la API del Sistema CMM (auth compartido).
 *
 * Adaptado de app/lib/api.ts del repo oficial sena-dev-2026-frontend.
 * El monitor reutiliza la API del Sistema CMM como proveedor de identidad
 * (login, refresh, magic links); este cliente NO se usa para los datos
 * del monitor, que siguen viniendo de nuestro backend (lib/api.ts).
 */

const CMM_API_BASE_URL =
  process.env.NEXT_PUBLIC_CMM_API_URL ?? "http://localhost:8001/api/v1";

/** Error de API con el mensaje del backend y el status HTTP. */
export class CmmApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "CmmApiError";
    this.status = status;
  }
}

interface CmmFetchOptions extends RequestInit {
  /** Access token JWT; si se pasa, va como Authorization: Bearer */
  token?: string;
}

/**
 * Wrapper sobre fetch para la API CMM.
 * Lanza CmmApiError con el `detail` del backend cuando la respuesta no es 2xx.
 */
export async function cmmFetch<T>(
  path: string,
  options: CmmFetchOptions = {}
): Promise<T> {
  const { token, ...init } = options;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...init.headers,
  };

  const response = await fetch(`${CMM_API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* respuesta sin JSON */
    }
    throw new CmmApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}
