"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "./sidebar";
import { SyncProgressProvider } from "./sync-progress";
import { DashboardPrefsProvider, useDashboardPrefs } from "./dashboard-prefs";
import { FICHAS_CHANGED_EVENT, fetchFichas } from "@/lib/api";
import { getAccessToken } from "@/lib/cmm-auth";
import type { FichaSummaryItem } from "@/types/api";

/** Cuerpo autenticado: aplica el ancho del sidebar como variable CSS. */
function ShellBody({
  fichas,
  children,
}: {
  fichas: FichaSummaryItem[];
  children: React.ReactNode;
}) {
  const { sidebarWidth } = useDashboardPrefs();
  return (
    <div
      className="min-h-screen"
      style={{ "--sidebar-w": `${sidebarWidth}px` } as React.CSSProperties}
    >
      <Sidebar fichas={fichas} />
      <main className="overflow-x-clip lg:pl-[var(--sidebar-w,16rem)]">
        {children}
      </main>
    </div>
  );
}

/** Rutas públicas de autenticación — sin sidebar y sin guard. */
const AUTH_ROUTES = ["/login", "/activar", "/auth/callback"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isAuthRoute = AUTH_ROUTES.some((r) => pathname.startsWith(r));

  const [fichas, setFichas] = useState<FichaSummaryItem[]>([]);
  // null = verificando; true/false = resultado
  const [authorized, setAuthorized] = useState<boolean | null>(null);

  // Guard de sesión (client-side, tokens en localStorage como el front CMM)
  useEffect(() => {
    if (isAuthRoute) return;
    if (getAccessToken()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- TODO(code-quality): guard de sesión lee localStorage (sistema externo) tras hidratar; necesario para evitar el flash del dashboard sin sesión
      setAuthorized(true);
    } else {
      setAuthorized(false);
      router.replace("/login");
    }
  }, [isAuthRoute, pathname, router]);

  useEffect(() => {
    if (isAuthRoute || !authorized) return;
    const load = () => {
      fetchFichas()
        .then(setFichas)
        .catch(() => {});
    };
    load();
    // Agregar o quitar un grupo cambia la lista sin recargar la página
    window.addEventListener(FICHAS_CHANGED_EVENT, load);
    return () => window.removeEventListener(FICHAS_CHANGED_EVENT, load);
  }, [isAuthRoute, authorized]);

  if (isAuthRoute) {
    return <>{children}</>;
  }

  if (!authorized) {
    // Verificando sesión o redirigiendo al login — evita el flash del dashboard
    return null;
  }

  return (
    <DashboardPrefsProvider>
      <SyncProgressProvider>
        <ShellBody fichas={fichas}>{children}</ShellBody>
      </SyncProgressProvider>
    </DashboardPrefsProvider>
  );
}
