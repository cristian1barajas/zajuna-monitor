"use client";

import { useEffect, useMemo, useState } from "react";
import { Topbar } from "@/components/layout/topbar";
import { StatsOverview } from "@/components/dashboard/stats-overview";
import { FichaSyncSelector } from "@/components/dashboard/ficha-sync-selector";
import { ZajunaAccountBanner } from "@/components/dashboard/zajuna-account-banner";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardPrefs } from "@/components/layout/dashboard-prefs";
import { fetchDashboard, fetchAlerts } from "@/lib/api";
import type { DashboardResponse, AlertItem } from "@/types/api";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { isFichaVisible } = useDashboardPrefs();

  useEffect(() => {
    Promise.all([fetchDashboard(), fetchAlerts()])
      .then(([dashboard, alertsRes]) => {
        setData(dashboard);
        setAlerts(alertsRes.alerts);
      })
      .catch((e) => setError(e.message));
  }, []);

  // Fichas visibles y KPIs recalculados solo sobre ellas
  const visibleFichas = useMemo(
    () => (data ? data.fichas.filter((f) => isFichaVisible(f.ficha)) : []),
    [data, isFichaVisible]
  );

  const kpis = useMemo(() => {
    const graded = visibleFichas.reduce((n, f) => n + f.total_graded, 0);
    const pending = visibleFichas.reduce((n, f) => n + f.total_pending, 0);
    const cells = graded + pending;
    return {
      totalFichas: visibleFichas.length,
      totalActive: visibleFichas.reduce((n, f) => n + f.total_active, 0),
      totalPending: pending,
      completion: cells > 0 ? Math.round((graded / cells) * 1000) / 10 : 0,
    };
  }, [visibleFichas]);

  if (error) {
    return (
      <>
        <Topbar title="Dashboard" />
        <div className="p-6">
          <div className="rounded-lg border border-danger-border bg-danger-soft p-4 text-sm text-danger-fg">
            Error al cargar datos: {error}
          </div>
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Topbar title="Dashboard" />
        <div className="space-y-5 p-6">
          <Skeleton className="h-24 rounded-2xl" />
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </>
    );
  }

  return (
    <>
      <Topbar title="Dashboard" lastScrape={data.last_scrape} />
      <div className="space-y-5 p-6">
        <ZajunaAccountBanner />
        <StatsOverview
          totalFichas={kpis.totalFichas}
          totalStudents={kpis.totalActive}
          totalPending={kpis.totalPending}
          overallCompletion={kpis.completion}
        />

        {/* Una sola tabla a todo el ancho; las alertas van dentro de cada ficha */}
        <FichaSyncSelector fichas={visibleFichas} alerts={alerts} />

        {visibleFichas.length < data.fichas.length && (
          <p className="text-xs text-muted-foreground">
            {data.fichas.length - visibleFichas.length} fichas ocultas con el ojo de la barra
            lateral.
          </p>
        )}
      </div>
    </>
  );
}
