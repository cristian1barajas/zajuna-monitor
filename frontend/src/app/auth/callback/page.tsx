"use client";

/**
 * Callback de SSO — handoff de sesión desde el portal de login del
 * Sistema CMM (Fase 2 del plan de auth compartido).
 *
 * El portal redirige aquí con los tokens en el fragment de la URL
 * (#access_token=...&refresh_token=...). El fragment nunca viaja al
 * servidor ni queda en logs. Se guarda la sesión, se limpia la URL y
 * se redirige según el rol.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getMe,
  saveSession,
  clearSession,
  canAccessMonitor,
} from "@/lib/cmm-auth";

const CMM_FRONT_URL = process.env.NEXT_PUBLIC_CMM_FRONT_URL ?? "";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");

    // Limpiar los tokens de la URL de inmediato
    window.history.replaceState(null, "", "/auth/callback");

    if (!accessToken || !refreshToken) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- TODO(code-quality): lectura del fragment de la URL (sistema externo) en el montaje; refactor a estado derivado requiere rediseño del handoff SSO
      setError("No se recibieron credenciales. Vuelve a iniciar sesión.");
      return;
    }

    saveSession({ access_token: accessToken, refresh_token: refreshToken });

    getMe(accessToken)
      .then((user) => {
        if (canAccessMonitor(user.role)) {
          router.replace("/");
        } else if (CMM_FRONT_URL) {
          window.location.href = CMM_FRONT_URL;
        } else {
          clearSession();
          setError(`Tu rol (${user.role}) no tiene acceso al monitor.`);
        }
      })
      .catch(() => {
        clearSession();
        setError("La sesión recibida no es válida. Vuelve a iniciar sesión.");
      });
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-8">
      <div className="text-center">
        {error ? (
          <>
            <p className="mb-4 text-sm font-medium text-danger-fg">{error}</p>
            <button
              onClick={() => router.replace("/login")}
              className="rounded-md bg-sena-green px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors duration-150 ease-out hover:bg-sena-green-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background dark:text-background dark:hover:bg-sena-green-light"
            >
              Ir al login
            </button>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Iniciando sesión…</p>
        )}
      </div>
    </main>
  );
}
