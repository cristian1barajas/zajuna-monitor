"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Image from "next/image";
import {
  LayoutDashboard,
  AlertTriangle,
  FolderPlus,
  KeyRound,
  Menu,
  X,
  ArrowLeft,
  Search,
  BookOpen,
  Activity,
  CalendarDays,
  FileSearch,
  Scale,
  GitCompareArrows,
  CheckSquare,
  FileWarning,
  Download,
  MessagesSquare,
  Eye,
  EyeOff,
} from "lucide-react";
import { cn, shortCourseName } from "@/lib/utils";
import { useCallback, useState } from "react";
import { UserBadge } from "./user-badge";
import { useDashboardPrefs } from "./dashboard-prefs";
import { useToGradeCounts } from "./use-to-grade";
import type { FichaSummaryItem } from "@/types/api";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/alertas", label: "Alertas", icon: AlertTriangle },
];

const SETTINGS_ITEMS = [
  { href: "/agregar-grupo", label: "Agregar grupo", icon: FolderPlus },
  { href: "/cuenta-zajuna", label: "Cuenta Zajuna", icon: KeyRound },
];

/** Secciones de la ficha agrupadas por lo que el instructor va a hacer. */
const FICHA_GROUPS = [
  {
    label: "Calificar",
    sections: [
      { slug: "pendientes-calificar", label: "Por calificar", icon: CheckSquare },
      { slug: "descargar-evidencias", label: "Descargar evidencias", icon: Download },
      { slug: "foros", label: "Foros", icon: MessagesSquare },
    ],
  },
  {
    label: "Seguimiento",
    sections: [
      { slug: "", label: "Resumen", icon: BookOpen },
      { slug: "actividad", label: "Actividad", icon: Activity },
      { slug: "cronograma", label: "Cronograma", icon: CalendarDays },
      { slug: "reportes", label: "Reportes", icon: FileSearch },
    ],
  },
  {
    label: "Trámites",
    sections: [
      { slug: "debido-proceso", label: "Debido proceso", icon: Scale },
      { slug: "informes-queja", label: "Informes de queja", icon: FileWarning },
      { slug: "juicios", label: "Juicios", icon: GitCompareArrows },
    ],
  },
];

function GroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-1.5 mt-5 px-3 text-[11px] font-semibold uppercase tracking-wider text-on-teal-muted">
      {children}
    </p>
  );
}

/** Conteo de entregas por calificar (última consulta de Por Calificar). */
function ToGradeBadge({ count, className }: { count: number; className?: string }) {
  return (
    <span
      title={`${count} ${count === 1 ? "entrega" : "entregas"} por calificar en la última consulta`}
      className={cn(
        "ml-auto inline-flex min-w-5 shrink-0 items-center justify-center rounded-full bg-sena-yellow px-1.5 text-[11px] font-bold tabular-nums text-sena-navy",
        className
      )}
    >
      {count}
    </span>
  );
}

interface NavItemProps {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  active: boolean;
  onNavigate: () => void;
  compact?: boolean;
  badge?: React.ReactNode;
}

function NavItem({ href, label, icon: Icon, active, onNavigate, compact, badge }: NavItemProps) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 text-sm transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        compact ? "py-1.5" : "py-2.5",
        active
          ? "bg-active-pill font-semibold text-white shadow-sm"
          : "text-on-teal hover:bg-sidebar-accent hover:text-white"
      )}
    >
      <Icon aria-hidden={true} className="h-4 w-4 flex-shrink-0" />
      <span className="truncate">{label}</span>
      {badge}
    </Link>
  );
}

interface SidebarProps {
  fichas: FichaSummaryItem[];
}

export function Sidebar({ fichas }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { isFichaVisible, toggleFichaVisible, setSidebarWidth } =
    useDashboardPrefs();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  // Arrastre del borde derecho para ajustar el ancho (solo desktop)
  const startResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const onMove = (ev: MouseEvent) => setSidebarWidth(ev.clientX);
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        document.body.style.userSelect = "";
      };
      document.body.style.userSelect = "none";
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [setSidebarWidth]
  );

  // Contexto de ficha: /fichas/<ficha>[/<seccion>[/...]]
  const routeFicha = pathname.startsWith("/fichas/")
    ? pathname.split("/")[2] ?? null
    : null;
  const routeSection = routeFicha ? pathname.split("/")[3] ?? "" : "";

  const currentFicha = fichas.find((f) => f.ficha === routeFicha);
  const toGrade = useToGradeCounts(fichas.map((f) => f.ficha));

  const filteredFichas = query.trim()
    ? fichas.filter(
        (f) =>
          f.ficha.includes(query.trim()) ||
          f.course_name.toLowerCase().includes(query.trim().toLowerCase())
      )
    : fichas;

  // Cambiar de ficha conservando la sección actual
  const switchFicha = (ficha: string) => {
    router.push(`/fichas/${ficha}${routeSection ? `/${routeSection}` : ""}`);
    setOpen(false);
  };

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setOpen(!open)}
        aria-label={open ? "Cerrar menú de navegación" : "Abrir menú de navegación"}
        aria-expanded={open}
        className={cn(
          "fixed left-3 top-3.5 z-50 cursor-pointer rounded-md p-2 transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden",
          open ? "text-white hover:bg-white/10" : "text-foreground hover:bg-accent"
        )}
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 z-40 h-screen w-64 bg-gradient-to-b from-sena-teal-deep via-sena-teal to-sena-teal text-sidebar-foreground transition-transform lg:w-[var(--sidebar-w,16rem)] lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Mango de redimensión (desktop) */}
        <div
          onMouseDown={startResize}
          className="absolute right-0 top-0 z-50 hidden h-full w-1.5 cursor-col-resize hover:bg-white/20 lg:block"
          title="Arrastra para ajustar el ancho"
        />
        <div className="flex h-full flex-col">
          {/* Brand */}
          <div className="border-b border-sidebar-border px-6 py-5">
            <Link
              href="/"
              className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Image
                src="/logo-sena-white.svg"
                alt="SENA"
                width={36}
                height={28}
                className="h-7 w-auto"
                priority
              />
              <span className="text-lg font-bold tracking-tight text-white">
                Zajuna Monitor
              </span>
            </Link>
          </div>

          <nav className="flex-1 overflow-y-auto px-3 py-4">
            {routeFicha ? (
              /* ============ MODO CONTEXTO DE FICHA ============ */
              <>
                <Link
                  href="/"
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-on-teal transition-colors duration-150 ease-out hover:bg-sidebar-accent hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                >
                  <ArrowLeft aria-hidden="true" className="h-4 w-4" />
                  Todas las fichas
                </Link>

                {/* Selector de ficha (conserva la sección al cambiar) */}
                <div className="mt-3 px-1">
                  <select
                    value={routeFicha}
                    onChange={(e) => switchFicha(e.target.value)}
                    className="w-full rounded-lg border border-white/15 bg-white/10 px-2.5 py-2 text-sm font-semibold text-white [&>option]:bg-background [&>option]:text-foreground transition-[border-color,box-shadow] duration-150 ease-out focus:outline-none focus:ring-2 focus:ring-ring"
                    aria-label="Cambiar de ficha"
                  >
                    {fichas.map((f) => (
                      <option key={f.ficha} value={f.ficha}>
                        {f.ficha} · {f.total_students} apr.
                      </option>
                    ))}
                    {!currentFicha && (
                      <option value={routeFicha}>{routeFicha}</option>
                    )}
                  </select>
                  {currentFicha && (
                    <p
                      className="mt-1.5 truncate px-1 text-[11px] text-on-teal-muted"
                      title={currentFicha.course_name}
                    >
                      {shortCourseName(currentFicha.course_name)}
                    </p>
                  )}
                </div>

                {/* Secciones de la ficha, agrupadas */}
                {FICHA_GROUPS.map((group) => (
                  <div key={group.label}>
                    <GroupLabel>{group.label}</GroupLabel>
                    <div className="space-y-0.5">
                      {group.sections.map((s) => {
                        const base = `/fichas/${routeFicha}`;
                        const href = s.slug ? `${base}/${s.slug}` : base;
                        // Coincidencia por segmento: /pendientes no debe activarse en /pendientes-calificar
                        const active = s.slug
                          ? pathname === href || pathname.startsWith(`${href}/`)
                          : pathname === base;
                        const count =
                          s.slug === "pendientes-calificar" ? toGrade.get(routeFicha) : undefined;
                        return (
                          <NavItem
                            key={s.slug}
                            href={href}
                            label={s.label}
                            icon={s.icon}
                            active={active}
                            onNavigate={() => setOpen(false)}
                            badge={count ? <ToGradeBadge count={count} /> : null}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))}

                {/* Lo global sigue a mano dentro de una ficha */}
                <div className="mt-5 space-y-0.5 border-t border-sidebar-border pt-3">
                  {[...NAV_ITEMS.slice(1), ...SETTINGS_ITEMS].map((item) => (
                    <NavItem
                      key={item.href}
                      {...item}
                      compact
                      active={pathname === item.href}
                      onNavigate={() => setOpen(false)}
                    />
                  ))}
                </div>
              </>
            ) : (
              /* ============ MODO GLOBAL ============ */
              <>
                <div className="space-y-1">
                  {NAV_ITEMS.map((item) => (
                    <NavItem
                      key={item.href}
                      {...item}
                      active={pathname === item.href}
                      onNavigate={() => setOpen(false)}
                    />
                  ))}
                </div>

                {fichas.length > 0 && (
                  <div className="mt-6">
                    <div className="mb-2 flex items-center justify-between px-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-on-teal-muted">
                        Fichas
                      </p>
                      <span
                        className="flex items-center gap-1 text-[10px] text-on-teal-muted"
                        title="El ojo muestra u oculta la ficha en el dashboard"
                      >
                        <Eye aria-hidden="true" className="h-3 w-3" />
                        dashboard
                      </span>
                    </div>

                    {/* Buscador */}
                    <div className="relative mb-2 px-1">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-on-teal-muted" />
                      <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Buscar ficha..."
                        className="w-full rounded-lg border border-white/15 bg-white/10 py-1.5 pl-8 pr-2 text-sm text-white transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-on-teal-muted focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>

                    <div className="space-y-0.5">
                      {filteredFichas.map((f) => {
                        const href = `/fichas/${f.ficha}`;
                        const visible = isFichaVisible(f.ficha);
                        return (
                          <div
                            key={f.ficha}
                            className={cn(
                              "group flex items-center rounded-lg text-sm text-on-teal transition-colors duration-150 ease-out hover:bg-sidebar-accent hover:text-white",
                              !visible && "opacity-45"
                            )}
                          >
                            <Link
                              href={href}
                              onClick={() => setOpen(false)}
                              className="flex min-w-0 flex-1 items-center justify-between rounded-md py-2 pl-3 pr-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                              title={shortCourseName(f.course_name)}
                            >
                              <span className="truncate font-mono text-[13px]">
                                {f.ficha}
                              </span>
                              {toGrade.get(f.ficha) ? (
                                <ToGradeBadge count={toGrade.get(f.ficha)!} />
                              ) : (
                                <span className="ml-2 text-xs tabular-nums opacity-70">
                                  {f.total_students}
                                </span>
                              )}
                            </Link>
                            <button
                              onClick={() => toggleFichaVisible(f.ficha)}
                              title={visible ? "Ocultar del dashboard" : "Mostrar en el dashboard"}
                              aria-label={
                                visible
                                  ? `Ocultar ficha ${f.ficha} del dashboard`
                                  : `Mostrar ficha ${f.ficha} en el dashboard`
                              }
                              className="flex h-8 w-8 flex-shrink-0 cursor-pointer items-center justify-center rounded-md transition-colors duration-150 ease-out hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                            >
                              {visible ? (
                                <Eye className="h-3.5 w-3.5" />
                              ) : (
                                <EyeOff className="h-3.5 w-3.5" />
                              )}
                            </button>
                          </div>
                        );
                      })}
                      {filteredFichas.length === 0 && (
                        <p className="px-3 py-2 text-xs text-on-teal-muted">
                          Sin resultados para “{query}”
                        </p>
                      )}
                    </div>
                  </div>
                )}

                <GroupLabel>Ajustes</GroupLabel>
                <div className="space-y-0.5">
                  {SETTINGS_ITEMS.map((item) => (
                    <NavItem
                      key={item.href}
                      {...item}
                      compact
                      active={pathname === item.href}
                      onNavigate={() => setOpen(false)}
                    />
                  ))}
                </div>
              </>
            )}
          </nav>

          {/* Usuario autenticado */}
          <UserBadge />

          {/* Institutional footer */}
          <div className="border-t border-sidebar-border px-6 py-4">
            <p className="text-[11px] leading-relaxed text-on-teal-muted">
              SENA · Servicio Nacional de Aprendizaje
            </p>
            <a
              href="https://zajuna.sena.edu.co"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-sm text-[11px] font-medium text-sena-green-light transition-colors duration-150 ease-out hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              zajuna.sena.edu.co
            </a>
          </div>
        </div>
      </aside>
    </>
  );
}
