"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, AlertTriangle, ArrowRight, CheckCircle2, Info } from "lucide-react";
import { useDashboardPrefs } from "@/components/layout/dashboard-prefs";
import { Topbar } from "@/components/layout/topbar";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { alertHref } from "@/lib/alerts";
import { fetchAlerts, fetchFichas, fetchHealth } from "@/lib/api";
import { cn, timeAgo } from "@/lib/utils";
import type { AlertItem, FichaSummaryItem, HealthResponse } from "@/types/api";

const SEVERITY = {
  critical: { icon: AlertCircle, className: "text-danger-fg", label: "Crítica" },
  warning: { icon: AlertTriangle, className: "text-warn-fg", label: "Advertencia" },
  info: { icon: Info, className: "text-info-fg", label: "Informativa" },
} as const;

type View = "accion" | "todas";

function severityOf(alert: AlertItem): keyof typeof SEVERITY {
  return alert.severity === "critical" || alert.severity === "warning" ? alert.severity : "info";
}

// La ruta es estática: useSearchParams necesita un Suspense alrededor
export default function AlertsPage() {
  return (
    <Suspense fallback={<Topbar title="Alertas" />}>
      <AlertsContent />
    </Suspense>
  );
}

function AlertsContent() {
  // ?ficha= llega desde la fila de una ficha en el dashboard
  const initialFicha = useSearchParams().get("ficha") ?? "";
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [fichas, setFichas] = useState<FichaSummaryItem[]>([]);
  const [selectedFicha, setSelectedFicha] = useState<string>(initialFicha);
  const [view, setView] = useState<View>("accion");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const { isFichaVisible } = useDashboardPrefs();

  useEffect(() => {
    // Cambiar el filtro re-consulta: se descarta la respuesta vieja para
    // que una petición lenta no pise a la del filtro vigente.
    let stale = false;
    Promise.all([fetchAlerts(selectedFicha || undefined), fetchHealth(), fetchFichas()])
      .then(([alertsRes, h, f]) => {
        if (stale) return;
        setAlerts(alertsRes.alerts);
        setHealth(h);
        setFichas(f);
        setLoading(false);
      })
      .catch((e) => {
        if (stale) return;
        setError(e.message);
        setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [selectedFicha]);

  if (error) {
    return (
      <>
        <Topbar title="Alertas" />
        <div className="p-6">
          <div className="rounded-lg border border-danger-border bg-danger-soft p-4 text-sm text-danger-fg">
            {error}
          </div>
        </div>
      </>
    );
  }

  if (loading) {
    return (
      <>
        <Topbar title="Alertas" />
        <div className="space-y-5 p-6">
          <Skeleton className="h-10 rounded-lg" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </>
    );
  }

  // Sin ficha elegida, mismas fichas que el dashboard: las ocultas con el ojo no cuentan
  const inScope = selectedFicha ? alerts : alerts.filter((a) => isFichaVisible(a.ficha));
  const hiddenCount = alerts.length - inScope.length;
  const actionable = inScope.filter((a) => a.severity === "critical" || a.severity === "warning");
  const rows = view === "accion" ? actionable : inScope;

  return (
    <>
      <Topbar
        title="Alertas"
        lastScrape={health?.last_scrape}
        description={
          health
            ? `Evidencias casi sin notas · última sincronización ${timeAgo(health.last_scrape)}. Cada fila te lleva a Por calificar con esa evidencia.`
            : "Evidencias casi sin notas en tus fichas."
        }
        actions={
          <>
            <label htmlFor="filtro-ficha" className="text-xs font-medium text-muted-foreground">
              Ficha
            </label>
            <select
              id="filtro-ficha"
              value={selectedFicha}
              onChange={(e) => setSelectedFicha(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 font-mono text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out focus:border-sena-green focus:ring-2 focus:ring-ring/30"
            >
              <option value="">Todas</option>
              {fichas.map((f) => (
                <option key={f.ficha} value={f.ficha}>
                  {f.ficha}
                </option>
              ))}
            </select>
          </>
        }
      />
      <div className="space-y-5 p-4 sm:p-6">
        <section className="overflow-hidden rounded-xl border bg-card shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <div role="radiogroup" aria-label="Qué alertas mostrar" className="inline-flex rounded-full border p-0.5">
              {(
                [
                  ["accion", `Críticas y advertencias (${actionable.length})`],
                  ["todas", `Todas (${inScope.length})`],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={view === value}
                  onClick={() => setView(value)}
                  className={cn(
                    "h-7 rounded-full px-3 text-xs font-medium tabular-nums transition-colors duration-150 ease-out",
                    view === value
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Crítica: nadie tiene nota · Advertencia: más del 80 % sin nota
              {hiddenCount > 0 && ` · ${hiddenCount} de fichas ocultas no se muestran`}
            </p>
          </div>

          {rows.length === 0 ? (
            <div className="flex items-center gap-2.5 px-4 py-6 text-sm text-muted-foreground">
              <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-ok-fg" />
              Sin alertas{view === "accion" ? " críticas ni advertencias" : ""}
              {selectedFicha ? ` en la ficha ${selectedFicha}` : ""}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32">Severidad</TableHead>
                  <TableHead className="w-24">Ficha</TableHead>
                  <TableHead>Evidencia</TableHead>
                  <TableHead className="hidden w-44 sm:table-cell">Sin nota</TableHead>
                  <TableHead className="w-24">
                    <span className="sr-only">Revisar</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((alert, i) => {
                  const sev = SEVERITY[severityOf(alert)];
                  const pct = Math.round(alert.percentage ?? 0);
                  return (
                    <TableRow key={`${alert.ficha}-${alert.type}-${alert.item_id ?? i}`}>
                      <TableCell>
                        <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", sev.className)}>
                          <sev.icon aria-hidden="true" className="h-3.5 w-3.5" />
                          {sev.label}
                        </span>
                      </TableCell>
                      <TableCell className="font-mono text-xs font-semibold">{alert.ficha}</TableCell>
                      <TableCell className="max-w-0 whitespace-normal">
                        <p className="text-sm leading-snug text-foreground">
                          {alert.evidence_name ?? alert.message}
                        </p>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {alert.pending_count != null ? (
                          <div
                            className="flex items-center gap-2"
                            title={`${alert.pending_count} aprendices sin nota`}
                          >
                            <div className="h-1.5 flex-1 rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-danger"
                                style={{ width: `${Math.min(pct, 100)}%` }}
                              />
                            </div>
                            <span className="w-16 text-right text-xs tabular-nums text-muted-foreground">
                              {alert.pending_count} · {pct}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Link
                          href={alertHref(alert)}
                          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-sena-green-dark hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-sena-green"
                        >
                          Revisar
                          <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </section>
      </div>
    </>
  );
}
