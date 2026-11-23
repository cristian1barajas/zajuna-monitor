"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { RapMappingUploader } from "@/components/juicios/rap-mapping-uploader";
import { SofiaUploader } from "@/components/juicios/sofia-uploader";
import { Loader2, CheckCircle2 } from "lucide-react";
import {
  fetchRapMapping,
  fetchSofiaReport,
  postRapMapping,
  postSofiaReport,
} from "@/lib/api";
import type {
  RapMappingInput,
  RapMappingResponse,
  SofiaReportInput,
  SofiaReportResponse,
} from "@/types/api";

// undefined = consultando; null = la ficha aún no tiene ese archivo
type Loaded<T> = T | null | undefined;

// Solo un 404 confirma que falta el archivo; otro error deja el estado desconocido
function notFound(e: unknown): boolean {
  return e instanceof Error && e.message.includes("404");
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("es-CO", { dateStyle: "medium" });
}

function LoadedNote({ loaded, detail }: { loaded: Loaded<unknown>; detail: string }) {
  if (loaded === undefined) return null;
  return (
    <p className="border-b bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
      {loaded ? `Ya cargado: ${detail}. Si subes otro, lo reemplaza.` : "Aún no hay datos cargados para esta ficha."}
    </p>
  );
}

export default function JuiciosUploadPage() {
  const params = useParams();
  const router = useRouter();
  const ficha = params.ficha as string;

  const [rapData, setRapData] = useState<RapMappingInput | null>(null);
  const [sofiaData, setSofiaData] = useState<SofiaReportInput | null>(null);
  const [saving, setSaving] = useState(false);
  const [rapSaved, setRapSaved] = useState(false);
  const [sofiaSaved, setSofiaSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rapLoaded, setRapLoaded] = useState<Loaded<RapMappingResponse>>(undefined);
  const [sofiaLoaded, setSofiaLoaded] = useState<Loaded<SofiaReportResponse>>(undefined);

  useEffect(() => {
    let cancelled = false;
    fetchRapMapping(ficha)
      .then((d) => !cancelled && setRapLoaded(d))
      .catch((e) => !cancelled && setRapLoaded(notFound(e) ? null : undefined));
    fetchSofiaReport(ficha)
      .then((d) => !cancelled && setSofiaLoaded(d))
      .catch((e) => !cancelled && setSofiaLoaded(notFound(e) ? null : undefined));
    return () => {
      cancelled = true;
    };
  }, [ficha]);

  // Vuelve a juicios con lo guardado; solo se queda si sabemos que falta el otro archivo
  const otherMissing = (!rapData && rapLoaded === null) || (!sofiaData && sofiaLoaded === null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      if (rapData && !rapSaved) {
        await postRapMapping(ficha, rapData);
        setRapSaved(true);
      }
      if (sofiaData && !sofiaSaved) {
        await postSofiaReport(ficha, sofiaData);
        setSofiaSaved(true);
      }

      if (!otherMissing) {
        router.push(`/fichas/${ficha}/juicios`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const canSave = (rapData && !rapSaved) || (sofiaData && !sofiaSaved);

  const savedBadge = (
    <span className="ml-auto inline-flex items-center gap-1 rounded-md border border-ok-border bg-ok-soft px-2 py-0.5 text-xs font-medium text-ok-fg">
      <CheckCircle2 aria-hidden="true" className="h-3 w-3" />
      Guardado
    </span>
  );

  return (
    <>
      <Topbar
        title="Cargar datos de juicios"
        description="Sube el mapeo de evidencias y el reporte de Sofia Plus para cruzar los juicios evaluativos de la ficha."
      />
      <div className="space-y-5 p-4 sm:p-6">

        <div className="grid gap-5 md:grid-cols-2">
          {/* RAP Mapping Uploader */}
          <section className="overflow-hidden rounded-xl border bg-card shadow-card">
            <div className="flex items-center gap-2 border-b px-4 py-3">
              <h3 className="text-sm font-semibold text-foreground">
                1. Mapeo Evidencias → RAP
              </h3>
              {rapSaved && savedBadge}
            </div>
            <LoadedNote
              loaded={rapLoaded}
              detail={
                rapLoaded
                  ? `${rapLoaded.stats.total_raps} RAPs, ${rapLoaded.stats.total_evidencias} evidencias · ${formatDate(rapLoaded.updated_at)}`
                  : ""
              }
            />
            <div className="p-4">
              <RapMappingUploader onParsed={setRapData} />
            </div>
          </section>

          {/* Sofia Report Uploader */}
          <section className="overflow-hidden rounded-xl border bg-card shadow-card">
            <div className="flex items-center gap-2 border-b px-4 py-3">
              <h3 className="text-sm font-semibold text-foreground">
                2. Reporte Juicios Sofia Plus
              </h3>
              {sofiaSaved && savedBadge}
            </div>
            <LoadedNote
              loaded={sofiaLoaded}
              detail={
                sofiaLoaded
                  ? `${sofiaLoaded.students_count} aprendices, ${sofiaLoaded.total_raps} RAPs · ${formatDate(sofiaLoaded.uploaded_at)}`
                  : ""
              }
            />
            <div className="p-4">
              <SofiaUploader onParsed={setSofiaData} />
            </div>
          </section>
        </div>

        {/* Summary + Save */}
        {(rapData || sofiaData) && (
          <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-card shadow-card px-4 py-3">
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
              {otherMissing && (
                <span className="w-full text-xs">
                  Para cruzar los juicios falta {rapData ? "el reporte de Sofia Plus" : "el mapeo de evidencias"}.
                </span>
              )}
              {rapData && (
                <span>
                  RAP:{" "}
                  <strong className="font-semibold tabular-nums text-foreground">
                    {rapData.stats.total_raps}
                  </strong>{" "}
                  RAPs,{" "}
                  <strong className="font-semibold tabular-nums text-foreground">
                    {rapData.stats.total_evidencias}
                  </strong>{" "}
                  evidencias
                </span>
              )}
              {sofiaData && (
                <span>
                  Sofia:{" "}
                  <strong className="font-semibold tabular-nums text-foreground">
                    {sofiaData.total_students}
                  </strong>{" "}
                  aprendices,{" "}
                  <strong className="font-semibold tabular-nums text-foreground">
                    {sofiaData.total_raps}
                  </strong>{" "}
                  RAPs
                </span>
              )}
            </div>
            <button
              onClick={handleSave}
              disabled={!canSave || saving}
              className={`inline-flex h-10 items-center gap-2 rounded-md bg-sena-green px-4 text-sm font-semibold text-white shadow-sm transition-colors duration-150 ease-out hover:bg-sena-green-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50 dark:text-background dark:hover:bg-sena-green-light ${
                !canSave || saving ? "cursor-not-allowed" : "cursor-pointer"
              }`}
            >
              {saving ? (
                <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
              )}
              {otherMissing ? "Guardar" : "Guardar y ver juicios"}
            </button>
          </section>
        )}

        {error && (
          <div
            role="alert"
            className="rounded-md border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium leading-snug text-danger-fg"
          >
            {error}
          </div>
        )}
      </div>
    </>
  );
}
