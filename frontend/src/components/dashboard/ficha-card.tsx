"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertCircle, AlertTriangle, CheckSquare, ChevronRight, FileSearch, Info } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { alertHref } from "@/lib/alerts";
import { cn, completionBg, completionColor, shortCourseName } from "@/lib/utils";
import type { AlertItem, FichaSummaryItem } from "@/types/api";

/** Columnas compartidas por la cabecera y las filas (desde md). */
export const FICHA_GRID =
  "md:grid md:grid-cols-[minmax(0,1fr)_4.5rem_5.5rem_6rem_6.5rem_9rem_7.5rem] md:items-center md:gap-4";

/** Alertas visibles al expandir una fila; el resto, en la página Alertas. */
const ALERTS_PREVIEW = 5;

const SEVERITY = {
  critical: { icon: AlertCircle, className: "text-danger-fg" },
  warning: { icon: AlertTriangle, className: "text-warn-fg" },
  info: { icon: Info, className: "text-info-fg" },
} as const;

interface FichaCardProps {
  ficha: FichaSummaryItem;
  /** Alertas de esta ficha, ya ordenadas por severidad. */
  alerts: AlertItem[];
  /** Entregas por calificar según la última consulta (null: nunca consultada). */
  toGrade: number | null;
  /** Modo selección: la fila muestra checkbox y alterna en vez de navegar. */
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: (ficha: string) => void;
}

function severityOf(alert: AlertItem): keyof typeof SEVERITY {
  return alert.severity === "critical" || alert.severity === "warning" ? alert.severity : "info";
}

/**
 * Fila de ficha del dashboard: identidad, métricas en columnas, alertas por
 * severidad, avance y accesos directos. Las alertas se ven al expandirla.
 */
export function FichaCard({
  ficha,
  alerts,
  toGrade,
  selectable = false,
  selected = false,
  onToggleSelect,
}: FichaCardProps) {
  const [open, setOpen] = useState(false);
  const pct = ficha.completion_percentage;
  const base = `/fichas/${ficha.ficha}`;
  const critical = alerts.filter((a) => a.severity === "critical").length;
  const warning = alerts.filter((a) => a.severity === "warning").length;

  return (
    <div
      className={cn(selected && "bg-accent")}
      onClick={selectable ? () => onToggleSelect?.(ficha.ficha) : undefined}
    >
      <div
        className={cn(
          "flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 transition-colors duration-150 ease-out",
          FICHA_GRID,
          selectable ? "cursor-pointer hover:bg-muted/60" : "hover:bg-muted/40",
        )}
      >
        {/* Identidad */}
        <div className="flex min-w-0 flex-1 items-center gap-3 md:flex-none">
          {selectable && (
            <Checkbox checked={selected} className="shrink-0" aria-label={`Seleccionar ficha ${ficha.ficha}`} />
          )}
          <div className="min-w-0">
            {selectable ? (
              <p className="font-mono text-sm font-semibold tracking-tight text-foreground">{ficha.ficha}</p>
            ) : (
              <Link
                href={base}
                className="rounded-sm font-mono text-sm font-semibold tracking-tight text-foreground hover:text-sena-green-dark hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:text-sena-green"
              >
                {ficha.ficha}
              </Link>
            )}
            <p className="truncate text-xs text-muted-foreground" title={ficha.course_name}>
              {shortCourseName(ficha.course_name)}
            </p>
          </div>
        </div>

        {/* Métricas: en móvil una línea compacta, desde md una columna cada una */}
        <p className="w-full text-[11px] text-muted-foreground md:hidden">
          {ficha.total_active} activos · {ficha.total_pending.toLocaleString()} sin nota
          {toGrade ? ` · ${toGrade} por calificar` : ""}
          {critical + warning > 0 ? ` · ${critical + warning} alertas` : ""}
        </p>
        <p className="hidden text-right text-sm font-semibold tabular-nums md:block">
          {ficha.total_active}
          {ficha.total_active !== ficha.total_students && (
            <span className="text-xs font-normal text-muted-foreground">/{ficha.total_students}</span>
          )}
        </p>
        <p
          className={cn(
            "hidden text-right text-sm font-semibold tabular-nums md:block",
            ficha.total_pending > 0 ? "text-foreground" : "text-muted-foreground",
          )}
        >
          {ficha.total_pending.toLocaleString()}
        </p>
        <p className="hidden text-right md:block">
          {toGrade === null ? (
            <span className="text-xs text-muted-foreground" title="Aún no consultas Por calificar en esta ficha">
              —
            </span>
          ) : toGrade > 0 ? (
            <span className="inline-flex min-w-7 justify-center rounded-full border border-danger-border bg-danger-soft px-2 py-0.5 text-xs font-bold tabular-nums text-danger-fg">
              {toGrade}
            </span>
          ) : (
            <span className="text-xs font-medium text-ok-fg">Al día</span>
          )}
        </p>
        <div className="hidden items-center justify-end gap-2.5 text-xs font-semibold tabular-nums md:flex">
          {critical > 0 && (
            <span className="inline-flex items-center gap-1 text-danger-fg" title={`${critical} críticas`}>
              <AlertCircle aria-hidden="true" className="h-3.5 w-3.5" />
              {critical}
            </span>
          )}
          {warning > 0 && (
            <span className="inline-flex items-center gap-1 text-warn-fg" title={`${warning} advertencias`}>
              <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />
              {warning}
            </span>
          )}
          {critical + warning === 0 && <span className="font-normal text-muted-foreground">—</span>}
        </div>

        {/* Avance */}
        <div className="flex w-28 shrink-0 items-center gap-2 md:w-auto">
          <div className="h-1.5 flex-1 rounded-full bg-muted">
            <div className={cn("h-full rounded-full", completionBg(pct))} style={{ width: `${Math.min(pct, 100)}%` }} />
          </div>
          <span className={cn("w-11 text-right text-sm font-semibold tabular-nums", completionColor(pct))}>
            {pct}%
          </span>
        </div>

        {/* Accesos y detalle */}
        {!selectable && (
          <div className="ml-auto flex items-center justify-end gap-1">
            <Link
              href={`${base}/pendientes-calificar`}
              title="Por calificar"
              aria-label={`Por calificar de la ficha ${ficha.ficha}`}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 ease-out hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <CheckSquare aria-hidden="true" className="h-4 w-4" />
            </Link>
            <Link
              href={`${base}/reportes`}
              title="Reportes"
              aria-label={`Reportes de la ficha ${ficha.ficha}`}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 ease-out hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <FileSearch aria-hidden="true" className="h-4 w-4" />
            </Link>
            <button
              type="button"
              disabled={alerts.length === 0}
              aria-expanded={open}
              aria-label={open ? "Ocultar alertas" : "Ver alertas"}
              onClick={() => setOpen((v) => !v)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 ease-out hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:invisible"
            >
              <ChevronRight
                aria-hidden="true"
                className={cn("h-4 w-4 transition-transform duration-150", open && "rotate-90")}
              />
            </button>
          </div>
        )}
      </div>

      {open && !selectable && (
        <div className="border-t bg-muted/30 px-4 py-3">
          <ul className="space-y-1.5">
            {alerts.slice(0, ALERTS_PREVIEW).map((alert, i) => {
              const sev = SEVERITY[severityOf(alert)];
              const href = alertHref(alert);
              return (
                <li key={`${alert.type}-${alert.item_id ?? i}`} className="flex items-start gap-2 text-xs">
                  <sev.icon aria-hidden="true" className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", sev.className)} />
                  <Link href={href} className="min-w-0 flex-1 leading-relaxed text-foreground hover:underline">
                    {alert.message}
                  </Link>
                </li>
              );
            })}
          </ul>
          {alerts.length > ALERTS_PREVIEW && (
            <Link
              href={`/alertas?ficha=${ficha.ficha}`}
              className="mt-2 inline-block text-xs font-medium text-sena-green-dark hover:underline dark:text-sena-green"
            >
              Ver las {alerts.length} alertas de esta ficha
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
