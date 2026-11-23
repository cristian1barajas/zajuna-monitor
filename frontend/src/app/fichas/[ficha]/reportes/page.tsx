"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  Clock,
  FileSearch,
  FileWarning,
  ListChecks,
  Loader2,
  Mail,
  ShieldAlert,
  UserX,
  X,
} from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { EvidencePicker } from "@/components/evidences/evidence-picker";
import { EmailPreviewModal } from "@/components/reports/email-preview-modal";
import { NovedadesDialog } from "@/components/reports/novedades-dialog";
import { OverdueStudentTable } from "@/components/reports/overdue-student-table";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchCronograma,
  fetchDueProcess,
  fetchFichaDetail,
  fetchHealth,
  fetchNovedades,
  postAdvanceDueProcess,
  postEmailDrafts,
  postNovedades,
  postReport,
  removeNovedades,
} from "@/lib/api";
import {
  owesOverHalf,
  type FilterMode,
  type StudentSubset,
} from "@/lib/overdue-students";
import { readEvidenceSelection, writeEvidenceSelection } from "@/lib/evidence-selection";
import { buildCutoffMap, compareGuides, guideOf } from "@/lib/pending-grading";
import { cn } from "@/lib/utils";
import type {
  CronogramaResponse,
  EmailDraft,
  FichaDetailResponse,
  NovedadRecord,
  ReportResponse,
} from "@/types/api";

function selectionKey(ids: Iterable<number>): string {
  return [...ids].sort((a, b) => a - b).join(",");
}

function formatDate(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

export default function ReportsPage() {
  const params = useParams();
  const ficha = params.ficha as string;

  const [fichaData, setFichaData] = useState<FichaDetailResponse | null>(null);
  const [cronograma, setCronograma] = useState<CronogramaResponse | null>(null);
  const [lastScrape, setLastScrape] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Evidencias del reporte (persisten por ficha)
  const [storedSelection, setStoredSelection] = useState<Set<number>>(() => readEvidenceSelection(ficha));
  const [pickerOpen, setPickerOpen] = useState(false);

  // Reporte
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [reportKey, setReportKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set());
  const [filterMode, setFilterMode] = useState<FilterMode>("overdue");
  // Por defecto, a quien se le puede escribir: activos y sin novedad
  const [subset, setSubset] = useState<StudentSubset>("activos");

  // Correos, debido proceso y novedades
  const [dueProcessMap, setDueProcessMap] = useState<Map<number, string>>(new Map());
  const [novedadRecords, setNovedadRecords] = useState<NovedadRecord[]>([]);
  const [novedadesOpen, setNovedadesOpen] = useState(false);
  const [emailDrafts, setEmailDrafts] = useState<EmailDraft[]>([]);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [emailLoading, setEmailLoading] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      fetchFichaDetail(ficha),
      fetchCronograma(ficha).catch(() => null),
      fetchHealth(),
      fetchDueProcess(ficha).catch(() => null),
      fetchNovedades(ficha).catch(() => null),
    ])
      .then(([detail, crono, health, dp, nov]) => {
        setFichaData(detail);
        setCronograma(crono);
        setLastScrape(health.last_scrape);
        if (dp?.records) {
          setDueProcessMap(new Map(dp.records.map((rec) => [rec.user_id, rec.current_stage])));
        }
        if (nov?.records) setNovedadRecords(nov.records);
      })
      .catch((e) => setError(e.message));
  }, [ficha]);

  useEffect(() => writeEvidenceSelection(ficha, storedSelection), [storedSelection, ficha]);

  const evidences = useMemo(() => fichaData?.evidences ?? [], [fichaData]);
  // Solo cuentan las evidencias que siguen existiendo en el curso
  const selectedEvIds = useMemo(() => {
    const valid = new Set(evidences.map((e) => e.item_id));
    return new Set([...storedSelection].filter((id) => valid.has(id)));
  }, [storedSelection, evidences]);
  const cutoffs = useMemo(() => buildCutoffMap(cronograma), [cronograma]);
  const novedadIds = useMemo(
    () => new Set(novedadRecords.map((r) => r.user_id)),
    [novedadRecords],
  );

  const selectionSummary = useMemo(() => {
    const chosen = evidences.filter((e) => selectedEvIds.has(e.item_id));
    const guides = [
      ...new Set(chosen.map((e) => guideOf(e.name)).filter((g): g is string => g !== null)),
    ].sort(compareGuides);
    const lastCutoff = chosen
      .map((e) => cutoffs.get(e.item_id))
      .filter((d): d is string => Boolean(d))
      .sort()
      .at(-1);
    return {
      guides: guides.length > 4 ? `${guides[0]} a ${guides.at(-1)}` : guides.join(", "),
      lastCutoff,
    };
  }, [evidences, selectedEvIds, cutoffs]);

  const stale = report !== null && reportKey !== selectionKey(selectedEvIds);

  const handleGenerateReport = async () => {
    if (selectedEvIds.size === 0) return;
    setLoading(true);
    setReportError(null);
    try {
      const result = await postReport(ficha, Array.from(selectedEvIds));
      setReport(result);
      setReportKey(selectionKey(selectedEvIds));
      setSelectedUserIds(new Set());
      setFilterMode("overdue");
      setSubset("activos");
    } catch (e) {
      setReportError(e instanceof Error ? e.message : "Error al generar reporte");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateEmails = async () => {
    setEmailLoading(true);
    setReportError(null);
    try {
      const result = await postEmailDrafts(ficha, Array.from(selectedUserIds), Array.from(selectedEvIds));
      setEmailDrafts(result.drafts);
      setShowEmailModal(true);
    } catch (e) {
      setReportError(e instanceof Error ? e.message : "Error al generar correos");
    } finally {
      setEmailLoading(false);
    }
  };

  const handleConfirmAdvance = async () => {
    setConfirmLoading(true);
    try {
      const result = await postAdvanceDueProcess(
        ficha,
        Array.from(selectedUserIds),
        Array.from(selectedEvIds),
      );
      setShowEmailModal(false);
      setSelectedUserIds(new Set());
      setDueProcessMap((prev) => {
        const map = new Map(prev);
        for (const rec of result.records) map.set(rec.user_id, rec.current_stage);
        return map;
      });
    } catch (e) {
      setReportError(e instanceof Error ? e.message : "Error al registrar avance");
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleMarkNovedad = async (userIds?: number[]) => {
    const ids = userIds ?? Array.from(selectedUserIds);
    try {
      const result = await postNovedades(ficha, ids, "cancelacion");
      setNovedadRecords(result.records);
      if (!userIds) setSelectedUserIds(new Set());
    } catch (e) {
      setReportError(e instanceof Error ? e.message : "Error al marcar novedad");
    }
  };

  const handleRemoveNovedad = async (userIds: number[]) => {
    try {
      const result = await removeNovedades(ficha, userIds);
      setNovedadRecords(result.records);
    } catch (e) {
      setReportError(e instanceof Error ? e.message : "Error al quitar novedad");
    }
  };

  if (error) {
    return (
      <>
        <Topbar title="Reportes" />
        <div className="p-6">
          <div className="rounded-lg border border-danger-border bg-danger-soft p-4 text-sm text-danger-fg">
            {error}
          </div>
        </div>
      </>
    );
  }

  if (!fichaData) {
    return (
      <>
        <Topbar title="Reportes" />
        <div className="space-y-4 p-6">
          <Skeleton className="h-20 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </>
    );
  }

  const evCount = report?.selected_evidences_count ?? selectedEvIds.size;
  const alerts: {
    subset: StudentSubset;
    count: number;
    label: string;
    icon: typeof UserX;
    tone: string;
  }[] = report
    ? [
        {
          subset: "suspendidos",
          count: report.students.filter((s) => s.status === "Suspendido" && s.overdue_count > 0).length,
          label: "suspendidos con pendientes",
          icon: UserX,
          tone: "border-danger-border bg-danger-soft text-danger-fg",
        },
        {
          subset: "inactivos",
          count: report.students.filter((s) => s.last_access_days >= 30 && s.overdue_count > 0).length,
          label: "con más de 30 días sin conectarse",
          icon: Clock,
          tone: "border-caution-border bg-caution-soft text-caution-fg",
        },
        {
          subset: "mitad",
          count: report.students.filter((s) => owesOverHalf(s, evCount)).length,
          label: "deben más de la mitad",
          icon: AlertTriangle,
          tone: "border-warn-border bg-warn-soft text-warn-fg",
        },
        {
          subset: "con_novedad",
          count: report.students.filter((s) => novedadIds.has(s.user_id)).length,
          label: "con novedad, excluidos de correos",
          icon: ShieldAlert,
          tone: "border-border bg-muted/50 text-muted-foreground",
        },
      ]
    : [];

  return (
    <>
      <Topbar
        title="Reportes"
        lastScrape={lastScrape}
        description="Elige las evidencias, genera el reporte de pendientes y gestiona los correos del debido proceso."
        actions={
          <Button variant="outline" size="sm" pill onClick={() => setNovedadesOpen(true)}>
            <ShieldAlert aria-hidden="true" className="text-caution-fg" />
            Novedades{novedadRecords.length > 0 && ` (${novedadRecords.length})`}
          </Button>
        }
      />
      {/* Sin overflow-hidden: la barra de acciones es sticky dentro de este contenedor */}
      <div className="min-w-0 space-y-5 p-4 sm:p-6">
        {/* Evidencias del reporte */}
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4 shadow-card">
          <div className="min-w-0">
            <p className="text-sm text-foreground">
              <span className="font-semibold tabular-nums">{selectedEvIds.size}</span> de{" "}
              <span className="tabular-nums">{evidences.length}</span> evidencias en el reporte
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {selectedEvIds.size === 0
                ? "Elige las evidencias que quieres evaluar."
                : [
                    selectionSummary.guides && `Guías ${selectionSummary.guides}`,
                    selectionSummary.lastCutoff &&
                      `cierres hasta el ${formatDate(selectionSummary.lastCutoff)}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => setPickerOpen(true)}>
              <ListChecks aria-hidden="true" />
              {selectedEvIds.size === 0 ? "Elegir evidencias" : "Cambiar"}
            </Button>
            <Button onClick={handleGenerateReport} disabled={selectedEvIds.size === 0 || loading}>
              {loading ? (
                <Loader2 aria-hidden="true" className="animate-spin" />
              ) : (
                <FileSearch aria-hidden="true" />
              )}
              {report && !stale ? "Actualizar reporte" : "Generar reporte"}
            </Button>
          </div>
          {stale && (
            <p className="w-full rounded-md border border-warn-border bg-warn-soft px-3 py-2 text-xs text-warn-fg">
              Cambiaste las evidencias después de generar el reporte. Genéralo de nuevo para
              actualizar la tabla.
            </p>
          )}
        </section>

        {reportError && (
          <div
            role="alert"
            className="rounded-md border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium leading-snug text-danger-fg"
          >
            {reportError}
          </div>
        )}

        {!report && !loading && (
          <p className="rounded-xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
            El reporte muestra quién debe cada evidencia elegida, su último acceso y su etapa de
            debido proceso.
          </p>
        )}

        {loading && !report && <Skeleton className="h-96 rounded-xl" />}

        {report && (
          <>
            <dl className="grid grid-cols-2 overflow-hidden rounded-xl border bg-card shadow-card sm:grid-cols-4">
              {[
                ["Evidencias", report.selected_evidences_count, "text-foreground"],
                ["Aprendices", report.total_students, "text-foreground"],
                [
                  "Con pendientes",
                  report.total_students_with_overdue,
                  report.total_students_with_overdue > 0 ? "text-caution-fg" : "text-muted-foreground",
                ],
                ["Al día", report.total_students - report.total_students_with_overdue, "text-ok-fg"],
              ].map(([label, value, tone], i) => (
                <div
                  key={label as string}
                  className={cn(
                    "px-4 py-3",
                    i < 2 && "border-b sm:border-b-0",
                    i % 2 === 0 && "border-r",
                    i === 1 && "sm:border-r",
                  )}
                >
                  <dt className="text-xs text-muted-foreground">{label}</dt>
                  <dd className={cn("mt-1 text-2xl font-bold tabular-nums tracking-tight", tone as string)}>
                    {value}
                  </dd>
                </div>
              ))}
            </dl>

            {alerts.some((a) => a.count > 0) && (
              <div className="flex flex-wrap items-center gap-2">
                {alerts
                  .filter((a) => a.count > 0)
                  .map((a) => {
                    const active = subset === a.subset;
                    return (
                      <button
                        key={a.subset}
                        type="button"
                        aria-pressed={active}
                        onClick={() => {
                          setSubset(active ? "activos" : a.subset);
                          setFilterMode(a.subset === "con_novedad" ? "all" : "overdue");
                        }}
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-shadow duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          a.tone,
                          active && "ring-2 ring-ring",
                        )}
                      >
                        <a.icon aria-hidden="true" className="h-3.5 w-3.5" />
                        <span className="font-semibold tabular-nums">{a.count}</span> {a.label}
                        {active && <X aria-hidden="true" className="h-3 w-3" />}
                      </button>
                    );
                  })}
              </div>
            )}

            <OverdueStudentTable
              students={report.students}
              selectedUserIds={selectedUserIds}
              onSelectedChange={setSelectedUserIds}
              dueProcessMap={dueProcessMap}
              novedadIds={novedadIds}
              onRemoveNovedad={(userId) => handleRemoveNovedad([userId])}
              filterMode={filterMode}
              onFilterModeChange={setFilterMode}
              subset={subset}
              onSubsetChange={setSubset}
              selectedEvidenceCount={evCount}
            />

            {/* Acciones fijas al pie mientras haya aprendices seleccionados */}
            {selectedUserIds.size > 0 && (
              <div className="sticky bottom-4 z-20 flex flex-wrap items-center gap-3 rounded-xl border bg-popover/95 px-4 py-3 text-popover-foreground shadow-pop backdrop-blur">
                <span className="text-sm font-medium tabular-nums">
                  {selectedUserIds.size} {selectedUserIds.size === 1 ? "aprendiz seleccionado" : "aprendices seleccionados"}
                </span>
                <div className="ml-auto flex flex-wrap items-center gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setSelectedUserIds(new Set())}>
                    Quitar selección
                  </Button>
                  <Button variant="outline" size="sm" pill onClick={() => handleMarkNovedad()}>
                    <ShieldAlert aria-hidden="true" className="text-caution-fg" />
                    Marcar novedad
                  </Button>
                  {/* Lleva a Informes de queja con las mismas evidencias y aprendices */}
                  <Link
                    href={`/fichas/${ficha}/informes-queja?evidences=${[...selectedEvIds].join(",")}&students=${[...selectedUserIds].join(",")}`}
                    className={buttonVariants({ variant: "outline", size: "sm", pill: true })}
                  >
                    <FileWarning aria-hidden="true" />
                    Informe de queja
                  </Link>
                  <Button size="sm" pill onClick={handleGenerateEmails} disabled={emailLoading}>
                    {emailLoading ? (
                      <Loader2 aria-hidden="true" className="animate-spin" />
                    ) : (
                      <Mail aria-hidden="true" />
                    )}
                    Generar correos
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <EvidencePicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        evidences={evidences}
        selected={selectedEvIds}
        onChange={setStoredSelection}
        cutoffs={cutoffs}
        title="Evidencias del reporte"
      />

      <NovedadesDialog
        open={novedadesOpen}
        onOpenChange={setNovedadesOpen}
        students={fichaData.students}
        novedadRecords={novedadRecords}
        onAdd={(ids) => handleMarkNovedad(ids)}
        onRemove={handleRemoveNovedad}
      />

      <EmailPreviewModal
        ficha={ficha}
        open={showEmailModal}
        onClose={() => setShowEmailModal(false)}
        drafts={emailDrafts}
        onConfirm={handleConfirmAdvance}
        confirming={confirmLoading}
      />
    </>
  );
}
