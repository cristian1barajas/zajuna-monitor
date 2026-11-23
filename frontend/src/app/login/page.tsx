"use client";

/**
 * Login del Zajuna Monitor contra la API del Sistema CMM (auth compartido).
 *
 * Pantalla adaptada del LoginView oficial del equipo ADSO 2026
 * (sena-dev-2026-frontend) — misma estructura de dos paneles, magic link
 * y accesibilidad; branding y tokens del monitor.
 *
 * Redirección por rol tras autenticar:
 *   - instructor / admin → dashboard del monitor
 *   - otros roles → front del Sistema CMM (NEXT_PUBLIC_CMM_FRONT_URL)
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Mail, Lock, ArrowRight } from "lucide-react";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import {
  loginUser,
  getMe,
  requestMagicLink,
  saveSession,
  clearSession,
  getAccessToken,
  canAccessMonitor,
} from "@/lib/cmm-auth";
import { CmmApiError } from "@/lib/cmm-api";

const CMM_FRONT_URL = process.env.NEXT_PUBLIC_CMM_FRONT_URL ?? "";

const BRAND_FEATURES = [
  "Semáforo de evidencias por ficha y aprendiz",
  "Juicios evaluativos cruzados con RAPs",
  "Reportes, alertas y debido proceso en un solo lugar",
] as const;

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [magicLinkSent, setMagicLinkSent] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);

  // Si ya hay sesión, saltar directo al dashboard
  useEffect(() => {
    if (getAccessToken()) {
      router.replace("/");
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- TODO(code-quality): guard de sesión lee localStorage (sistema externo) tras hidratar; evita el flash del dashboard
      setCheckingAuth(false);
    }
  }, [router]);

  const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const tokens = await loginUser({ email, password });
      saveSession(tokens);

      // Redirección por rol
      const user = await getMe(tokens.access_token);
      if (canAccessMonitor(user.role)) {
        router.push("/");
      } else if (CMM_FRONT_URL) {
        window.location.href = CMM_FRONT_URL;
      } else {
        clearSession();
        setError(
          `Tu rol (${user.role}) no tiene acceso al Zajuna Monitor. ` +
            "Ingresa desde el Sistema CMM."
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

  const handleMagicLink = async () => {
    if (!email) {
      setError("Ingresa tu correo institucional primero");
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await requestMagicLink(email);
      setMagicLinkSent(true);
    } catch (err) {
      setError(
        err instanceof CmmApiError ? err.message : "Error al enviar el enlace"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (checkingAuth) return null;

  return (
    <div className="relative isolate grid min-h-screen grid-cols-1 overflow-hidden bg-gradient-to-br from-sena-teal-deep via-sena-teal to-sena-teal-light lg:grid-cols-[1.05fr_1fr]">
      <LoginPattern />
      {/* Franja de identificación del gobierno colombiano */}
      <div
        aria-hidden="true"
        className="fixed inset-x-0 top-0 z-50 grid h-1 grid-cols-3"
      >
        <div className="bg-flag-yellow" />
        <div className="bg-flag-blue" />
        <div className="bg-flag-red" />
      </div>

      {/* ══════════ Panel de marca ══════════ */}
      <aside
        aria-label="Identidad institucional SENA"
        className="relative flex min-h-[300px] flex-col justify-between gap-10 px-8 py-10 lg:min-h-screen lg:px-14 lg:py-12"
      >
        {/* Cabecera: logo + producto */}
        <div className="flex items-center gap-4">
          <Image
            src="/logo-sena-white.svg"
            alt="SENA"
            width={44}
            height={34}
            className="h-9 w-auto"
            priority
          />
          <div aria-hidden="true" className="h-9 w-px bg-teal-hairline" />
          <div className="leading-tight">
            <p className="text-sm font-semibold text-white">Zajuna Monitor</p>
            <p className="text-xs text-on-teal-muted">
              Servicio Nacional de Aprendizaje
            </p>
          </div>
        </div>

        {/* Hero */}
        <div className="max-w-[540px]">
          <h1 className="text-[2rem] font-bold leading-[1.05] tracking-tight text-white [text-wrap:balance] lg:text-[clamp(2.5rem,4.2vw,3.5rem)]">
            Tus fichas, <span className="text-sena-green-light">al día</span>,
            sin abrir Zajuna.
          </h1>
          <p className="mt-5 max-w-[440px] text-base leading-relaxed text-on-teal-muted lg:text-[17px]">
            Seguimiento de calificaciones, evidencias pendientes y juicios
            evaluativos de todas tus fichas en un solo tablero.
          </p>
          <ul className="mt-9 hidden border-y border-teal-hairline lg:block">
            {BRAND_FEATURES.map((feature) => (
              <li
                key={feature}
                className="flex items-center gap-3 border-b border-teal-hairline py-3.5 text-sm text-on-teal-muted last:border-b-0"
              >
                <span
                  aria-hidden="true"
                  className="h-1.5 w-1.5 shrink-0 rounded-full bg-sena-green"
                />
                {feature}
              </li>
            ))}
          </ul>
        </div>

        {/* Pie del panel */}
        <p className="text-xs text-on-teal-muted">
          <span className="font-semibold text-on-teal-muted">
            Zajuna Monitor
          </span>{" "}
          · Autenticación Sistema CMM · Centro Metalmecánico
        </p>
      </aside>

      {/* ══════════ Panel de formulario ══════════ */}
      <main className="relative flex items-center justify-center px-6 pb-14 lg:min-h-screen lg:px-12 lg:py-14">
        <div className="fixed right-4 top-4 z-40">
          <ThemeToggle />
        </div>

        <div
          id="login-form"
          className="w-full max-w-[440px] rounded-2xl border border-white/20 bg-white/10 p-7 shadow-pop backdrop-blur-md animate-in fade-in slide-in-from-bottom-2 duration-500 ease-out sm:p-9"
        >
          <Image
            src="/logo-sena-white.svg"
            alt=""
            width={44}
            height={34}
            className="mx-auto h-11 w-auto"
          />
          <h1 className="mt-4 text-center text-3xl font-bold tracking-tight text-white">
            Bienvenido
          </h1>
          <p className="mb-8 mt-2 text-center text-sm font-medium leading-relaxed text-on-teal">
            Ingresa con tu cuenta institucional del Sistema CMM para acceder al
            monitor.
          </p>

          {error && (
            <div
              role="alert"
              className="mb-5 rounded-md border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium leading-snug text-danger-fg"
            >
              {error}
            </div>
          )}

          {magicLinkSent && (
            <div
              role="status"
              className="mb-5 rounded-md border border-ok-border bg-ok-soft px-4 py-3 text-sm font-medium leading-snug text-ok-fg"
            >
              Revisa tu correo — te enviamos el enlace de acceso.
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="mb-4">
              <label
                htmlFor="email"
                className="mb-1.5 block text-[13px] font-semibold text-white"
              >
                Correo institucional
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  id="email"
                  type="email"
                  className="h-12 w-full rounded-lg border border-transparent bg-card shadow-card pl-9 pr-3 text-sm text-card-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground focus:border-sena-green focus:ring-2 focus:ring-sena-green-light/50"
                  placeholder="ejemplo@sena.edu.co"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setError(null);
                  }}
                />
              </div>
            </div>

            <div className="mb-5">
              <label
                htmlFor="password"
                className="mb-1.5 block text-[13px] font-semibold text-white"
              >
                Contraseña
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  id="password"
                  type="password"
                  className="h-12 w-full rounded-lg border border-transparent bg-card shadow-card pl-9 pr-3 text-sm text-card-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground focus:border-sena-green focus:ring-2 focus:ring-sena-green-light/50"
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError(null);
                  }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className={`group flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-active-pill text-sm font-semibold text-white shadow-sm transition-colors duration-150 ease-out hover:bg-sena-green-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-sena-teal ${
                isSubmitting ? "cursor-not-allowed opacity-70" : "cursor-pointer"
              }`}
            >
              {isSubmitting ? "Ingresando…" : "Ingresar"}
              {!isSubmitting && (
                <ArrowRight className="h-4 w-4 transition-transform duration-150 ease-out group-hover:translate-x-0.5" />
              )}
            </button>

            <div className="my-6 flex items-center gap-3 text-xs text-on-teal-muted">
              <span className="h-px flex-1 bg-white/20" />
              o
              <span className="h-px flex-1 bg-white/20" />
            </div>

            <button
              type="button"
              onClick={handleMagicLink}
              disabled={isSubmitting || magicLinkSent}
              className={`flex h-12 w-full items-center justify-center gap-2 rounded-lg border text-sm font-medium transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white ${
                magicLinkSent
                  ? "cursor-default border-ok-border bg-ok-soft text-ok-fg"
                  : "cursor-pointer border-white/40 bg-transparent text-white hover:bg-white/10"
              }`}
            >
              <Mail className="h-4 w-4" />
              {magicLinkSent
                ? "Enlace enviado — revisa tu correo"
                : "Enviarme un enlace mágico"}
            </button>
          </form>

          <div
            role="note"
            className="mt-8 rounded-lg border border-white/15 bg-black/10 px-4 py-3 text-xs leading-relaxed text-on-teal"
          >
            <strong className="font-semibold text-white">
              ¿Primera vez?
            </strong>{" "}
            Tu cuenta la crea el administrador del centro. Recibirás un correo
            con un enlace para establecer tu contraseña.
          </div>
        </div>
      </main>
    </div>
  );
}

/** Patrón de marca decorativo (D4: sin fotos del SENA). */
function LoginPattern() {
  return (
    <svg
      aria-hidden="true"
      className="pointer-events-none absolute -bottom-40 -left-40 -z-10 h-[640px] w-[640px] text-white/[0.05]"
      viewBox="0 0 640 640"
      fill="none"
    >
      {[90, 170, 250, 320].map((r) => (
        <circle key={r} cx="320" cy="320" r={r} stroke="currentColor" strokeWidth="40" />
      ))}
    </svg>
  );
}
