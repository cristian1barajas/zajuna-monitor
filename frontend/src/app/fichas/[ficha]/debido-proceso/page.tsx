"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FileDown } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { DueProcessTable } from "@/components/due-process/due-process-table";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { fetchDueProcess, fetchHealth } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DueProcessRecord } from "@/types/api";

export default function DueProcessPage() {
  const params = useParams();
  const ficha = params.ficha as string;

  const [records, setRecords] = useState<DueProcessRecord[]>([]);
  const [lastScrape, setLastScrape] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState("all");

  useEffect(() => {
    Promise.all([fetchDueProcess(ficha), fetchHealth()])
      .then(([dp, health]) => {
        setRecords(dp.records);
        setLastScrape(health.last_scrape);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [ficha]);

  const filtered =
    stageFilter === "all"
      ? records
      : records.filter((r) => r.current_stage === stageFilter);

  const countByStage = (stage: string) =>
    records.filter((r) => r.current_stage === stage).length;

  if (error) {
    return (
      <>
        <Topbar title="Debido proceso" />
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
        <Topbar title="Debido proceso" />
        <div className="space-y-4 p-6">
          <Skeleton className="h-20 rounded-lg" />
          <Skeleton className="h-96 rounded-lg" />
        </div>
      </>
    );
  }

  // Cada cifra filtra la tabla; "Total en proceso" quita el filtro.
  // Los bordes por celda mantienen las hairlines correctas cuando la
  // rejilla envuelve (2 columnas en móvil, 5 en escritorio).
  const tiles = [
    {
      stage: "all",
      label: "Total en proceso",
      count: records.length,
      color: "text-foreground",
      borderClass: "border-b border-r sm:border-b-0",
    },
    {
      stage: "primer_llamado",
      label: "1er llamado",
      count: countByStage("primer_llamado"),
      color: "text-warn-fg",
      borderClass: "border-b sm:border-b-0 sm:border-r",
    },
    {
      stage: "segundo_llamado",
      label: "2do llamado",
      count: countByStage("segundo_llamado"),
      color: "text-caution-fg",
      borderClass: "border-b border-r sm:border-b-0",
    },
    {
      stage: "plan_mejoramiento",
      label: "Plan mejoramiento",
      count: countByStage("plan_mejoramiento"),
      color: "text-danger-fg",
      borderClass: "border-b sm:border-b-0 sm:border-r",
    },
    {
      stage: "comite",
      label: "Comité",
      count: countByStage("comite"),
      color: "text-notice-fg",
      borderClass: "",
    },
  ];

  return (
    <>
      <Topbar
        title="Debido proceso"
        lastScrape={lastScrape}
        description="Seguimiento de los llamados de atención registrados desde la página de reportes."
        actions={
          <Link
            href={`/fichas/${ficha}/debido-proceso/soportes`}
            className={buttonVariants({
              variant: "outline-primary",
              size: "sm",
            })}
          >
            <FileDown aria-hidden="true" /> Soportes de Outlook (PDF)
          </Link>
        }
      />
      <div className="space-y-5 p-4 sm:p-6">
        <div
          role="group"
          aria-label="Filtrar por etapa"
          className="grid grid-cols-2 overflow-hidden rounded-xl border bg-card shadow-card sm:grid-cols-5"
        >
          {tiles.map((tile) => {
            const active = stageFilter === tile.stage;
            return (
              <button
                key={tile.stage}
                type="button"
                aria-pressed={active}
                onClick={() => setStageFilter(active ? "all" : tile.stage)}
                className={cn(
                  "px-4 py-3 text-left transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                  tile.borderClass,
                  active
                    ? "bg-accent shadow-[inset_0_-2px_0_var(--primary)]"
                    : "hover:bg-muted/50"
                )}
              >
                <span className="block text-xs text-muted-foreground">
                  {tile.label}
                </span>
                <span
                  className={cn(
                    "mt-1 block text-2xl font-bold tabular-nums tracking-tight",
                    tile.count > 0 ? tile.color : "text-muted-foreground"
                  )}
                >
                  {tile.count}
                </span>
              </button>
            );
          })}
        </div>

        <DueProcessTable
          records={filtered}
          ficha={ficha}
          filtered={stageFilter !== "all" && records.length > 0}
        />
      </div>
    </>
  );
}
