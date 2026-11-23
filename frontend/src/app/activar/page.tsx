"use client";

/**
 * Activación de cuenta / restablecimiento de contraseña vía magic link.
 *
 * El correo de invitación del Sistema CMM trae un enlace con ?token=...
 * Esta página pide la nueva contraseña, la establece contra la API CMM
 * (/auth/magic-link/verify) y deja la sesión iniciada.
 */

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import { Lock } from "lucide-react";
import {
  verifyMagicLink,
  getMe,
  saveSession,
  clearSession,
  canAccessMonitor,
} from "@/lib/cmm-auth";
import { CmmApiError } from "@/lib/cmm-api";

const CMM_FRONT_URL = process.env.NEXT_PUBLIC_CMM_FRONT_URL ?? "";

function ActivarForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres");
      return;
    }
    if (password !== confirm) {
      setError("Las contraseñas no coinciden");
      return;
    }
    setIsSubmitting(true);
    try {
      const tokens = await verifyMagicLink(token, password);
      saveSession(tokens);
      const user = await getMe(tokens.access_token);
      if (canAccessMonitor(user.role)) {
        router.push("/");
      } else if (CMM_FRONT_URL) {
        window.location.href = CMM_FRONT_URL;
      } else {
        clearSession();
        setError(
          `Cuenta activada, pero tu rol (${user.role}) no tiene acceso al monitor.`
        );
      }
    } catch (err) {
      setError(
        err instanceof CmmApiError
          ? err.message
          : "Error de conexión con el servidor de autenticación"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-8">
      <div className="w-full max-w-[400px]">
        <div className="mb-6 flex items-center gap-3">
          <Image
            src="/logo-sena-green.svg"
            alt="SENA"
            width={36}
            height={28}
            className="h-8 w-auto dark:hidden"
          />
          <Image
            src="/logo-sena-white.svg"
            alt="SENA"
            width={36}
            height={28}
            className="hidden h-8 w-auto dark:block"
          />
          <span className="text-lg font-semibold">Zajuna Monitor</span>
        </div>

        <h1 className="mb-2 text-2xl font-bold tracking-tight text-foreground">
          Establece tu contraseña
        </h1>
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Define la contraseña con la que ingresarás al Zajuna Monitor y al
          Sistema CMM.
        </p>

        {!token && (
          <div
            role="alert"
            className="mb-5 rounded-md border border-warn-border bg-warn-soft px-4 py-3 text-sm font-medium leading-snug text-warn-fg"
          >
            Falta el token de activación. Abre esta página desde el enlace que
            recibiste en tu correo.
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="mb-5 rounded-md border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium leading-snug text-danger-fg"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="mb-4">
            <label
              htmlFor="password"
              className="mb-1.5 block text-[13px] font-medium text-foreground"
            >
              Nueva contraseña
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="password"
                type="password"
                className="h-11 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground/70 focus:border-sena-green focus:ring-2 focus:ring-ring/30"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setError(null);
                }}
              />
            </div>
          </div>

          <div className="mb-6">
            <label
              htmlFor="confirm"
              className="mb-1.5 block text-[13px] font-medium text-foreground"
            >
              Confirmar contraseña
            </label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="confirm"
                type="password"
                className="h-11 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground/70 focus:border-sena-green focus:ring-2 focus:ring-ring/30"
                autoComplete="new-password"
                required
                minLength={8}
                value={confirm}
                onChange={(e) => {
                  setConfirm(e.target.value);
                  setError(null);
                }}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !token}
            className={`flex h-11 w-full items-center justify-center gap-2 rounded-md bg-sena-green text-sm font-semibold text-white shadow-sm transition-colors duration-150 ease-out hover:bg-sena-green-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background dark:text-background dark:hover:bg-sena-green-light ${
              isSubmitting || !token
                ? "cursor-not-allowed opacity-70"
                : "cursor-pointer"
            }`}
          >
            {isSubmitting ? "Activando…" : "Activar cuenta"}
          </button>
        </form>
      </div>
    </main>
  );
}

export default function ActivatePage() {
  return (
    <Suspense fallback={null}>
      <ActivarForm />
    </Suspense>
  );
}
