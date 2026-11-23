"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { useParams, useSearchParams } from "next/navigation";
import { Download, Loader2 } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { Skeleton } from "@/components/ui/skeleton";
import { AssignmentPicker } from "@/components/download-evidences/assignment-picker";
import { DownloadConfig } from "@/components/download-evidences/download-config";
import {
  SubmissionsTable,
  downloadableSubmissions,
} from "@/components/download-evidences/submissions-table";
import { DownloadProgress } from "@/components/download-evidences/download-progress";
import { GradingPrompt } from "@/components/download-evidences/grading-prompt";
import { LoadingSteps } from "@/components/download-evidences/loading-steps";
import {
  fetchAssignments,
  fetchSubmissions,
  startEvidenceDownload,
} from "@/lib/api";
import type {
  AssignmentMapping,
  SubmissionsListResponse,
} from "@/types/api";

const DEFAULT_DIR_KEY = "zajuna_download_dir";

// ?cmid= (desde Por calificar) preselecciona y carga esa tarea
function readCmidParam(search: URLSearchParams): number | null {
  const value = Number(search.get("cmid"));
  return Number.isInteger(value) && value > 0 ? value : null;
}

export default function DownloadEvidencesPage() {
  const params = useParams();
  const ficha = params.ficha as string;

  // Evidence list from assignments mapping
  const [assignments, setAssignments] = useState<AssignmentMapping[] | null>(null);
  // useSearchParams ve la URL nueva al llegar navegando desde Por calificar
  const searchParams = useSearchParams();
  const [initialCmid] = useState(() => readCmidParam(searchParams));
  const [selectedCmid, setSelectedCmid] = useState<number | null>(initialCmid);

  // Submissions data
  const [submissions, setSubmissions] = useState<SubmissionsListResponse | null>(null);
  const [loadingSubmissions, setLoadingSubmissions] = useState(false);

  // Download config
  const [targetDir, setTargetDir] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(DEFAULT_DIR_KEY) || "C:\\Users\\crist\\Downloads\\Zajuna";
      // Strip any trailing ficha number from previously saved paths
      return saved.replace(/\\?\d{7}$/, "");
    }
    return "C:\\Users\\crist\\Downloads\\Zajuna";
  });
  const [includeInstrument, setIncludeInstrument] = useState(true);
  const [selectedStatuses, setSelectedStatuses] = useState<Set<string>>(new Set());

  // Download state
  const [jobId, setJobId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [completedFolderPath, setCompletedFolderPath] = useState<string | null>(null);
  const [loadingStep, setLoadingStep] = useState(0);

  const [error, setError] = useState<string | null>(null);

  // Save targetDir to localStorage
  useEffect(() => {
    if (typeof window !== "undefined" && targetDir) {
      localStorage.setItem(DEFAULT_DIR_KEY, targetDir);
    }
  }, [targetDir]);

  // Fetch submissions for one assignment
  const loadSubmissions = useCallback(
    async (cmid: number) => {
      setLoadingSubmissions(true);
      setLoadingStep(1);
      setSubmissions(null);
      setJobId(null);
      setCompletedFolderPath(null);
      setError(null);

      // Simulate step progression while waiting for the API
      const stepTimer1 = setTimeout(() => setLoadingStep(2), 4000);
      const stepTimer2 = setTimeout(() => setLoadingStep(3), 10000);
      const stepTimer3 = setTimeout(() => setLoadingStep(4), 18000);

      try {
        const data = await fetchSubmissions(ficha, cmid);
        setSubmissions(data);
        // Default: select "Enviado para calificar" if available
        const defaultStatuses = new Set<string>();
        for (const s of data.statuses) {
          if (s === "Enviado para calificar") defaultStatuses.add(s);
        }
        if (defaultStatuses.size === 0 && data.statuses.length > 0) {
          defaultStatuses.add(data.statuses[0]);
        }
        setSelectedStatuses(defaultStatuses);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Error al cargar envíos");
      } finally {
        clearTimeout(stepTimer1);
        clearTimeout(stepTimer2);
        clearTimeout(stepTimer3);
        setLoadingSubmissions(false);
        setLoadingStep(0);
      }
    },
    [ficha],
  );

  // Load assignments (and the one from ?cmid= if it is a task of this ficha)
  useEffect(() => {
    let cancelled = false;
    fetchAssignments(ficha)
      .then((data) => {
        if (cancelled) return;
        // Only show assignments (not forums) since we download files
        const assigns = data.assignments.filter((a) => a.module_type === "assign");
        setAssignments(assigns);
        if (initialCmid === null) return;
        if (assigns.some((a) => a.cmid === initialCmid)) loadSubmissions(initialCmid);
        else setSelectedCmid(null);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [ficha, initialCmid, loadSubmissions]);

  // Start download (de la tarea cargada, aunque luego se haya elegido otra en la lista)
  const handleDownload = async () => {
    if (!submissions || !targetDir) return;
    setDownloading(true);
    setError(null);
    try {
      const result = await startEvidenceDownload(ficha, {
        cmid: submissions.cmid,
        target_dir: `${targetDir}\\${ficha}`,
        include_instrument: includeInstrument,
        status_filter: [...selectedStatuses],
      });
      setJobId(result.job_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al iniciar descarga");
      setDownloading(false);
    }
  };

  const handleDownloadComplete = useCallback((folderPath?: string) => {
    setDownloading(false);
    if (folderPath) setCompletedFolderPath(folderPath);
  }, []);

  // Count files to download
  const toDownload = submissions
    ? downloadableSubmissions(submissions.submissions, selectedStatuses)
    : [];
  const filesToDownload = toDownload.reduce((sum, s) => sum + s.file_count, 0);
  const instrumentCount =
    includeInstrument && submissions?.instrument_available ? 1 : 0;
  const totalDownload = filesToDownload + instrumentCount;

  // Loading state
  if (error && !assignments) {
    return (
      <>
        <Topbar title="Descargar evidencias" />
        <div className="p-6">
          <div className="rounded-lg border border-danger-border bg-danger-soft p-4 text-sm text-danger-fg">
            {error}
          </div>
        </div>
      </>
    );
  }

  if (!assignments) {
    return (
      <>
        <Topbar title="Descargar evidencias" />
        <div className="space-y-4 p-6">
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </>
    );
  }

  return (
    <>
      <Topbar
        title="Descargar evidencias"
        description="Elige una tarea y descarga sus envíos en el estado que necesites. Los archivos se guardan con nombre incremental y el nombre del aprendiz."
      />
      <div className="space-y-5 p-4 sm:p-6">

        {error && (
          <div
            role="alert"
            className="rounded-md border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium leading-snug text-danger-fg"
          >
            {error}
          </div>
        )}

        <AssignmentPicker
          assignments={assignments}
          selectedCmid={selectedCmid}
          onSelect={setSelectedCmid}
          onLoad={() => {
            if (selectedCmid) loadSubmissions(selectedCmid);
          }}
          loading={loadingSubmissions}
        />

        {!submissions && !loadingSubmissions && (
          <div className="flex min-h-[200px] items-center justify-center rounded-xl border border-dashed bg-card p-8 shadow-card">
            <div className="text-center text-muted-foreground">
              <Download aria-hidden="true" className="mx-auto mb-2 h-8 w-8 opacity-50" />
              <p className="text-sm">Elige una tarea y pulsa &quot;Ver envíos&quot;</p>
            </div>
          </div>
        )}

        {loadingSubmissions && <LoadingSteps current={loadingStep} />}

        {submissions && (
          <section className="rounded-xl border bg-card shadow-card">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b px-4 py-3">
              <h3 className="min-w-0 text-sm font-semibold text-foreground">
                {submissions.assignment_name}
              </h3>
              <span className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
                {submissions.total_submissions} aprendices
              </span>
            </div>

            <div className="border-b px-4 py-3">
              <DownloadConfig
                targetDir={targetDir}
                onTargetDirChange={setTargetDir}
                ficha={ficha}
                includeInstrument={includeInstrument}
                onIncludeInstrumentChange={setIncludeInstrument}
                instrumentAvailable={submissions.instrument_available}
                statuses={submissions.statuses}
                selectedStatuses={selectedStatuses}
                onStatusesChange={setSelectedStatuses}
              />
            </div>

            <SubmissionsTable submissions={toDownload} />

            <div className="border-t px-4 py-3">
              {jobId ? (
                <DownloadProgress
                  ficha={ficha}
                  jobId={jobId}
                  onComplete={handleDownloadComplete}
                />
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm tabular-nums text-muted-foreground">
                    {toDownload.length} {toDownload.length === 1 ? "aprendiz" : "aprendices"} con archivos ·{" "}
                    {filesToDownload} {filesToDownload === 1 ? "archivo" : "archivos"}
                  </p>
                  <Button
                    onClick={handleDownload}
                    disabled={totalDownload === 0 || downloading || !targetDir}
                  >
                    {downloading ? (
                      <Loader2 aria-hidden="true" className="animate-spin" />
                    ) : (
                      <Download aria-hidden="true" />
                    )}
                    Descargar ({totalDownload} archivo{totalDownload !== 1 ? "s" : ""})
                  </Button>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Grade prompt - shown after download completes */}
        {completedFolderPath && !downloading && (
          <GradingPrompt folderPath={completedFolderPath} />
        )}
      </div>
    </>
  );
}
