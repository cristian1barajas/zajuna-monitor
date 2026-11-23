"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Clock, Home } from "lucide-react";
import { timeAgo } from "@/lib/utils";
import { SyncButton } from "./sync-button";
import { ThemeToggle } from "./theme-toggle";

interface TopbarProps {
  /** Nombre de la sección; la ficha ya va en las migas de pan. */
  title: string;
  /** Una o dos frases de contexto bajo el título. */
  description?: React.ReactNode;
  /** Acciones propias de la página, a la derecha del título. */
  actions?: React.ReactNode;
  lastScrape?: string | null;
}

const PAGE_LABELS: Record<string, string> = {
  alertas: "Alertas",
  "agregar-grupo": "Agregar grupo",
  "cuenta-zajuna": "Cuenta Zajuna",
  pendientes: "Sin nota",
  actividad: "Actividad",
  cronograma: "Cronograma",
  reportes: "Reportes",
  "debido-proceso": "Debido proceso",
  soportes: "Soportes de Outlook",
  juicios: "Juicios",
  upload: "Cargar datos",
  "pendientes-calificar": "Por calificar",
  "informes-queja": "Informes de queja",
  "descargar-evidencias": "Descargar evidencias",
  foros: "Foros",
};

interface Crumb {
  label: string;
  href: string;
}

/** Migas de pan derivadas de la ruta: /fichas/3607707/juicios → Ficha 3607707 › Juicios. */
function crumbsFor(pathname: string): Crumb[] {
  const parts = pathname.split("/").filter(Boolean);
  const crumbs: Crumb[] = [];
  let href = "";
  for (let i = 0; i < parts.length; i++) {
    href += `/${parts[i]}`;
    if (parts[i] === "fichas") continue;
    const label =
      parts[i - 1] === "fichas"
        ? `Ficha ${decodeURIComponent(parts[i])}`
        : PAGE_LABELS[parts[i]] ?? decodeURIComponent(parts[i]);
    crumbs.push({ label, href });
  }
  return crumbs;
}

/**
 * Encabezado único de cada página: la franja de migas de pan y acciones
 * globales queda fija al hacer scroll; debajo van el título de la sección,
 * su descripción y las acciones propias de la página.
 */
export function Topbar({ title, description, actions, lastScrape }: TopbarProps) {
  const pathname = usePathname();
  const crumbs = crumbsFor(pathname);

  // La franja fija va fuera del <header>: sticky solo se pega dentro de su
  // contenedor, y el header mide lo mismo que su contenido.
  return (
    <>
      <div className="sticky top-0 z-30 flex min-h-14 items-center justify-between gap-3 bg-background/95 py-2 pl-[3.75rem] pr-4 backdrop-blur sm:pr-6 lg:pl-6">
        <nav aria-label="Ruta de navegación" className="min-w-0">
          <ol className="flex min-w-0 items-center gap-1.5 text-xs font-semibold">
            <li className="shrink-0">
              <Link
                href="/"
                aria-label="Inicio"
                className="flex rounded-sm text-muted-foreground transition-colors duration-150 ease-out hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Home aria-hidden="true" className="h-4 w-4" />
              </Link>
            </li>
            {(crumbs.length ? crumbs : [{ label: "Inicio", href: "/" }]).map((c, i, all) => {
              const last = i === all.length - 1;
              return (
                <li key={c.href} className="flex min-w-0 items-center gap-1.5">
                  <ChevronRight aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  {last ? (
                    <span aria-current="page" className="truncate text-sena-green-dark dark:text-sena-green">
                      {c.label}
                    </span>
                  ) : (
                    <Link
                      href={c.href}
                      className="truncate rounded-sm text-sena-green-dark transition-colors duration-150 ease-out hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-sena-green"
                    >
                      {c.label}
                    </Link>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          {lastScrape !== undefined && (
            <div className="hidden items-center gap-1.5 text-xs tabular-nums text-muted-foreground sm:flex">
              <Clock aria-hidden="true" className="h-3.5 w-3.5" />
              <span>{timeAgo(lastScrape ?? null)}</span>
            </div>
          )}
          <ThemeToggle />
          <SyncButton />
        </div>
      </div>
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3 px-4 pb-1 pt-2 sm:px-6">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{title}</h1>
          {description && (
            <div className="mt-1 max-w-[72ch] text-sm leading-relaxed text-muted-foreground">
              {description}
            </div>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
    </>
  );
}
