"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { StudentTable } from "@/components/fichas/student-table";
import { EvidenceTable } from "@/components/fichas/evidence-table";
import { Heatmap } from "@/components/fichas/heatmap";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, completionBg, completionColor, shortCourseName } from "@/lib/utils";
import { fetchCronograma, fetchFichaDetail, fetchHealth } from "@/lib/api";
import { buildCutoffMap } from "@/lib/pending-grading";
import { SyncButton } from "@/components/layout/sync-button";
import type { CronogramaResponse, FichaDetailResponse } from "@/types/api";

const TABS = ["students", "evidences", "heatmap"] as const;

/** ?tab=evidencias abre directo en esa pestaña (llega desde la antigua página Sin nota). */
function initialTab(search: URLSearchParams): string {
  const tab = search.get("tab");
  if (tab === "evidencias") return "evidences";
  return TABS.includes(tab as (typeof TABS)[number]) ? (tab as string) : "students";
}

export default function FichaDetailPage() {
  const params = useParams();
  const ficha = params.ficha as string;
  const [data, setData] = useState<FichaDetailResponse | null>(null);
  const [lastScrape, setLastScrape] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cronograma, setCronograma] = useState<CronogramaResponse | null>(null);
  // useSearchParams (no window.location): al navegar dentro de la app la URL
  // del navegador todavía no cambió cuando se monta la página
  const searchParams = useSearchParams();
  const [tab] = useState(() => initialTab(searchParams));
  const cutoffs = useMemo(() => buildCutoffMap(cronograma), [cronograma]);

  useEffect(() => {
    Promise.all([fetchFichaDetail(ficha), fetchHealth()])
      .then(([detail, health]) => {
        setData(detail);
        setLastScrape(health.last_scrape);
      })
      .catch((e) => setError(e.message));
    fetchCronograma(ficha)
      .then(setCronograma)
      .catch(() => {}); // Sin cronograma, Evidencias no filtra por cierre
  }, [ficha]);

  if (error) {
    return (
      <>
        <Topbar title={`Ficha ${ficha}`} />
        <div className="p-6">
          <div className="rounded-lg border border-danger-border bg-danger-soft p-4 text-sm text-danger-fg">
            {error}
          </div>
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Topbar title={`Ficha ${ficha}`} />
        <div className="space-y-4 p-6">
          <Skeleton className="h-20 rounded-lg" />
          <Skeleton className="h-96 rounded-lg" />
        </div>
      </>
    );
  }

  return (
    <>
      <Topbar
        title={`Ficha ${ficha}`}
        lastScrape={lastScrape}
        description={<span title={data.course_name}>{shortCourseName(data.course_name)}</span>}
        actions={<SyncButton fichas={[ficha]} label="Actualizar" compact />}
      />
      <div className="space-y-5 p-4 sm:p-6">

        {/* KPIs: banda dividida por reglas de 1px, cifras tabulares */}
        <dl className="grid grid-cols-3 divide-x overflow-hidden rounded-xl border bg-card shadow-card">
          <div className="px-4 py-4 sm:px-6">
            <dt className="text-xs text-muted-foreground">
              {data.total_active !== data.total_students
                ? `Activos de ${data.total_students}`
                : "Aprendices"}
            </dt>
            <dd className="mt-1 text-2xl font-bold tabular-nums tracking-tight text-foreground">
              {data.total_active}
            </dd>
          </div>
          <div className="px-4 py-4 sm:px-6">
            <dt className="text-xs text-muted-foreground">Evidencias</dt>
            <dd className="mt-1 text-2xl font-bold tabular-nums tracking-tight text-foreground">
              {data.total_evidences}
            </dd>
          </div>
          <div className="px-4 py-4 sm:px-6">
            <dt className="text-xs text-muted-foreground">
              Avance de calificación
            </dt>
            <dd
              className={cn(
                "mt-1 text-2xl font-bold tabular-nums tracking-tight",
                completionColor(data.completion_percentage)
              )}
            >
              {data.completion_percentage}
              <span className="text-sm font-semibold">%</span>
            </dd>
            <div
              aria-hidden="true"
              className="mt-2 h-1 max-w-[160px] overflow-hidden rounded-full bg-muted"
            >
              <div
                className={cn(
                  "h-full rounded-full",
                  completionBg(data.completion_percentage)
                )}
                style={{
                  width: `${Math.min(data.completion_percentage, 100)}%`,
                }}
              />
            </div>
          </div>
        </dl>

        {/* Tabs */}
        <Tabs defaultValue={tab}>
          <TabsList>
            <TabsTrigger value="students">Aprendices</TabsTrigger>
            <TabsTrigger value="evidences">Evidencias</TabsTrigger>
            <TabsTrigger value="heatmap">Heatmap</TabsTrigger>
          </TabsList>

          <TabsContent value="students" className="mt-4">
            <StudentTable students={data.students} />
          </TabsContent>

          <TabsContent value="evidences" className="mt-4">
            {/* key: el filtro "Ya cerró" por defecto se decide cuando llega el cronograma */}
            <EvidenceTable
              key={cutoffs.size > 0 ? "con-cronograma" : "sin-cronograma"}
              evidences={data.evidences}
              students={data.students}
              cutoffs={cutoffs}
            />
          </TabsContent>

          <TabsContent value="heatmap" className="mt-4">
            <Heatmap students={data.students} evidences={data.evidences} ficha={ficha} courseName={data.course_name} />
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
