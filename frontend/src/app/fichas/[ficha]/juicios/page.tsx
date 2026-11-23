"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Topbar } from "@/components/layout/topbar";
import { RapSummaryCards } from "@/components/juicios/rap-summary-cards";
import { StudentRapTable } from "@/components/juicios/student-rap-table";
import { RapViewTable } from "@/components/juicios/rap-view-table";
import { RapHeatmap } from "@/components/juicios/rap-heatmap";
import { JuiciosPorAsignar } from "@/components/juicios/juicios-por-asignar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchRapCross } from "@/lib/api";
import { Upload, AlertCircle } from "lucide-react";
import type { RapStatus } from "@/components/juicios/student-filters";
import type { RapCrossResponse } from "@/types/api";

export default function JuiciosPage() {
  const params = useParams();
  const ficha = params.ficha as string;
  const [data, setData] = useState<RapCrossResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [retryKey, setRetryKey] = useState(0);
  const [tab, setTab] = useState("sofia");
  const [statusFilter, setStatusFilter] = useState<RapStatus | null>(null);

  // Las cifras del resumen filtran la vista por aprendiz
  const selectStatus = (status: RapStatus | null) => {
    setStatusFilter(status);
    if (status) setTab("students");
  };

  useEffect(() => {
    let cancelled = false;
    fetchRapCross(ficha)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ficha, retryKey]);

  const retry = () => {
    setLoading(true);
    setError(null);
    setRetryKey((k) => k + 1);
  };

  if (loading) {
    return (
      <>
        <Topbar title="Juicios" />
        <div className="space-y-5 p-6">
          <Skeleton className="h-9 w-72 rounded-md" />
          <Skeleton className="h-20 rounded-lg" />
          <Skeleton className="h-96 rounded-lg" />
        </div>
      </>
    );
  }

  if (error) {
    // Likely 404: no data uploaded yet
    const is404 = error.includes("404");
    return (
      <>
        <Topbar title="Juicios" />
        <div className="p-6">
          <section className="rounded-xl border bg-card shadow-card">
            <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-6 py-14 text-center">
              <AlertCircle
                aria-hidden="true"
                className={`h-10 w-10 ${is404 ? "text-muted-foreground" : "text-danger-fg"}`}
              />
              <div>
                <h3 className="text-lg font-semibold tracking-tight text-foreground">
                  {is404
                    ? "No hay datos de juicios cargados"
                    : "Error al cargar datos"}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {is404
                    ? "Primero debes cargar el mapeo de evidencias (Excel) y el reporte de juicios de Sofia Plus."
                    : error}
                </p>
              </div>
              {is404 ? (
                <Link
                  href={`/fichas/${ficha}/juicios/upload`}
                  className="inline-flex h-10 items-center gap-2 rounded-md bg-sena-green px-4 text-sm font-semibold text-white shadow-sm transition-colors duration-150 ease-out hover:bg-sena-green-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background dark:text-background dark:hover:bg-sena-green-light"
                >
                  <Upload aria-hidden="true" className="h-4 w-4" />
                  Cargar datos
                </Link>
              ) : (
                <Button
                  variant="outline"
                  pill
                  onClick={retry}
                >
                  Reintentar
                </Button>
              )}
            </div>
          </section>
        </div>
      </>
    );
  }

  if (!data) return null;

  return (
    <>
      <Topbar
        title="Juicios"
        description={
          <>
            <span className="font-medium tabular-nums text-foreground">
              {data.total_students}
            </span>{" "}
            aprendices ·{" "}
            <span className="font-medium tabular-nums text-foreground">
              {data.total_raps}
            </span>{" "}
            RAPs analizados
          </>
        }
        actions={
          <Link
            href={`/fichas/${ficha}/juicios/upload`}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-input bg-background px-3 text-sm font-medium text-foreground transition-colors duration-150 ease-out hover:border-sena-green hover:bg-sena-green-tint hover:text-sena-green-darker focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background dark:hover:text-sena-green-light"
          >
            <Upload aria-hidden="true" className="h-4 w-4" />
            Actualizar datos
          </Link>
        }
      />
      <div className="space-y-5 p-4 sm:p-6">

        {/* Franja de KPIs */}
        <RapSummaryCards
          summary={data.summary}
          totalRaps={data.total_raps}
          totalStudents={data.total_students}
          activeStatus={statusFilter}
          onSelectStatus={selectStatus}
        />

        {/* Tabs */}
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="sofia">Asignar en Sofía</TabsTrigger>
            <TabsTrigger value="students">Por aprendiz</TabsTrigger>
            <TabsTrigger value="raps">Por RAP</TabsTrigger>
            <TabsTrigger value="heatmap">Heatmap</TabsTrigger>
          </TabsList>

          <TabsContent value="sofia" className="mt-4">
            <JuiciosPorAsignar ficha={ficha} />
          </TabsContent>

          <TabsContent value="students" className="mt-4">
            <StudentRapTable
              students={data.students}
              statusFilter={statusFilter}
              onClearStatus={() => setStatusFilter(null)}
            />
          </TabsContent>

          <TabsContent value="raps" className="mt-4">
            <RapViewTable students={data.students} />
          </TabsContent>

          <TabsContent value="heatmap" className="mt-4">
            <RapHeatmap students={data.students} ficha={ficha} />
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
