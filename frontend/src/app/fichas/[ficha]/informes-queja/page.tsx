"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowRight, Download, ListChecks, Loader2, Search } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { EvidencePicker } from "@/components/evidences/evidence-picker";
import { CandidateTable } from "@/components/complaint-reports/candidate-table";
import { ReportDataForm } from "@/components/complaint-reports/report-data-form";
import { StepSection } from "@/components/complaint-reports/step-section";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchComplaintCandidates,
  fetchComplaintEvidences,
  fetchCronograma,
  generateComplaintReports,
} from "@/lib/api";
import { getAccessToken, getMe } from "@/lib/cmm-auth";
import { buildCutoffMap } from "@/lib/pending-grading";
import type { ComplaintCandidate, CronogramaResponse, EvidenceItem } from "@/types/api";

type Step = 1 | 2 | 3;

/** Selección de evidencias de Reportes: punto de partida cuando no llega por URL. */
const REPORT_SELECTION_KEY = "zajuna_report_evidences_";

function readIds(raw: string | null): number[] {
  return (raw ?? "")
    .split(",")
    .map(Number)
    .filter((n) => Number.isInteger(n) && n > 0);
}

/** ?evidences=1,2&students=3,4 llegan desde la barra de acciones de Reportes. */
function readHandoff(search: URLSearchParams): { evidences: number[]; students: number[] } {
  return { evidences: readIds(search.get("evidences")), students: readIds(search.get("students")) };
}

function readReportSelection(ficha: string): number[] {
  try {
    const raw = localStorage.getItem(REPORT_SELECTION_KEY + ficha);
    return raw ? (JSON.parse(raw) as number[]) : [];
  } catch {
    return [];
  }
}

function searchKey(evidenceIds: Set<number>, minDays: number): string {
  return `${[...evidenceIds].sort((a, b) => a - b).join(",")}|${minDays}`;
}

export default function ComplaintReportsPage() {
  const params = useParams();
  const ficha = params.ficha as string;
  // Se lee una vez al montar; no cambia mientras la página está abierta
  const searchParams = useSearchParams();
  const [handoff] = useState(() => readHandoff(searchParams));

  const [evidences, setEvidences] = useState<EvidenceItem[] | null>(null);
  const [cronograma, setCronograma] = useState<CronogramaResponse | null>(null);
  const [selectedEvidences, setSelectedEvidences] = useState<Set<number>>(
    () =>
      new Set(
        handoff.evidences.length > 0
          ? handoff.evidences
          : typeof window === "undefined"
            ? []
            : readReportSelection(ficha),
      ),
  );
  const [pickerOpen, setPickerOpen] = useState(false);
  const [minDaysInactive, setMinDaysInactive] = useState(20);

  const [step, setStep] = useState<Step>(1);
  const [candidates, setCandidates] = useState<ComplaintCandidate[] | null>(null);
  const [candidatesKey, setCandidatesKey] = useState("");
  const [selectedStudents, setSelectedStudents] = useState<Set<number>>(new Set());
  const [searching, setSearching] = useState(false);

  const [coordinatorName, setCoordinatorName] = useState("ING FREDY HERNANDO ARIAS AYALA");
  // El informe lo firma el instructor de la sesión (perfil del CMM).
  const [instructorName, setInstructorName] = useState("");
  const [reportDate, setReportDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    getMe(token)
      .then((user) => setInstructorName(user.full_name.toUpperCase()))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchComplaintEvidences(ficha)
      .then(setEvidences)
      .catch((e) => setError(e.message));
    fetchCronograma(ficha)
      .then(setCronograma)
      .catch(() => {}); // Sin cronograma no hay filtro de cierre
  }, [ficha]);

  const cutoffs = useMemo(() => buildCutoffMap(cronograma), [cronograma]);
  // Solo cuentan las evidencias que esta página puede evaluar
  const validEvidences = useMemo(() => {
    const valid = new Set((evidences ?? []).map((e) => e.item_id));
    return new Set([...selectedEvidences].filter((id) => valid.has(id)));
  }, [selectedEvidences, evidences]);
  const stale = candidates !== null && candidatesKey !== searchKey(validEvidences, minDaysInactive);

  const runSearch = useCallback(
    async (evidenceIds: Set<number>, preselect: number[] = []) => {
      if (evidenceIds.size === 0) return;
      setSearching(true);
      setError(null);
      setGenerated(false);
      try {
        const res = await fetchComplaintCandidates(ficha, [...evidenceIds], minDaysInactive);
        const found = new Set(res.candidates.map((c) => c.user_id));
        const chosen = preselect.filter((id) => found.has(id));
        setCandidates(res.candidates);
        setCandidatesKey(searchKey(evidenceIds, minDaysInactive));
        setSelectedStudents(new Set(chosen));
        setStep(chosen.length > 0 ? 3 : 2);
      } catch (e) {
        setError(e instanceof Error ? e.message : "No se pudieron buscar los candidatos");
      } finally {
        setSearching(false);
      }
    },
    [ficha, minDaysInactive],
  );

  // Llegando desde Reportes con evidencias y aprendices: buscar de una vez
  const autoSearched = useRef(false);
  useEffect(() => {
    if (autoSearched.current || !evidences || handoff.students.length === 0) return;
    autoSearched.current = true;
    void runSearch(validEvidences, handoff.students);
  }, [evidences, validEvidences, runSearch, handoff]);

  const handleGenerate = async () => {
    if (selectedStudents.size === 0) return;
    setGenerating(true);
    setError(null);
    try {
      // La fecha va en los documentos como DD-MM-YYYY
      const [y, m, d] = reportDate.split("-");
      const blob = await generateComplaintReports(
        ficha,
        [...selectedStudents],
        [...validEvidences],
        coordinatorName,
        instructorName,
        `${d}-${m}-${y}`,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Informes_Queja_${ficha}_${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setGenerated(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron generar los informes");
    } finally {
      setGenerating(false);
    }
  };

  if (error && !evidences) {
    return (
      <>
        <Topbar title="Informes de queja" />
        <div className="p-6">
          <div className="rounded-lg border border-danger-border bg-danger-soft p-4 text-sm text-danger-fg">
            {error}
          </div>
        </div>
      </>
    );
  }

  if (!evidences) {
    return (
      <>
        <Topbar title="Informes de queja" />
        <div className="space-y-4 p-6">
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-16 rounded-xl" />
        </div>
      </>
    );
  }

  return (
    <>
      <Topbar
        title="Informes de queja"
        description="Por faltas académicas: elige las evidencias, revisa los aprendices inactivos que las deben y genera los informes Word para coordinación."
      />
      <div className="min-w-0 space-y-4 p-4 sm:p-6">
        {error && (
          <div
            role="alert"
            className="rounded-md border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium leading-snug text-danger-fg"
          >
            {error}
          </div>
        )}

        <StepSection
          n={1}
          title="Evidencias y umbral"
          active={step === 1}
          done={candidates !== null}
          summary={`${validEvidences.size} evidencias · ${minDaysInactive} días o más sin conectarse`}
          onEdit={() => setStep(1)}
        >
          <div className="flex flex-wrap items-end justify-between gap-4 p-4">
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <p className="text-sm text-foreground">
                  <span className="font-semibold tabular-nums">{validEvidences.size}</span> de{" "}
                  <span className="tabular-nums">{evidences.length}</span> evidencias
                </p>
                <Button variant="outline" size="sm" pill className="mt-1.5" onClick={() => setPickerOpen(true)}>
                  <ListChecks aria-hidden="true" />
                  {validEvidences.size === 0 ? "Elegir evidencias" : "Cambiar"}
                </Button>
              </div>
              <div>
                <label htmlFor="min-dias-inactivo" className="mb-1.5 block text-[13px] font-medium text-foreground">
                  Días sin conectarse (mínimo)
                </label>
                <input
                  id="min-dias-inactivo"
                  type="number"
                  min={1}
                  value={minDaysInactive}
                  onChange={(e) => setMinDaysInactive(Number(e.target.value) || 1)}
                  className="h-9 w-28 rounded-md border border-input bg-background px-3 text-sm tabular-nums text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out focus:border-sena-green focus:ring-2 focus:ring-ring/30"
                />
              </div>
            </div>
            <Button onClick={() => runSearch(validEvidences)} disabled={validEvidences.size === 0 || searching}>
              {searching ? <Loader2 aria-hidden="true" className="animate-spin" /> : <Search aria-hidden="true" />}
              Buscar candidatos
            </Button>
          </div>
        </StepSection>

        <StepSection
          n={2}
          title="Aprendices"
          active={step === 2}
          done={selectedStudents.size > 0 && !stale}
          summary={
            candidates === null
              ? undefined
              : stale
                ? "Cambiaste las evidencias o el umbral: busca de nuevo"
                : `${selectedStudents.size} de ${candidates.length} candidatos seleccionados`
          }
          onEdit={candidates !== null && !stale ? () => setStep(2) : undefined}
        >
          {candidates && (
            <>
              <div className="p-4">
                <CandidateTable
                  candidates={candidates}
                  selected={selectedStudents}
                  onSelectionChange={setSelectedStudents}
                />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
                <span className="text-sm text-muted-foreground">
                  <span className="font-semibold tabular-nums text-foreground">{selectedStudents.size}</span> de{" "}
                  {candidates.length} seleccionados
                </span>
                <Button onClick={() => setStep(3)} disabled={selectedStudents.size === 0}>
                  Siguiente
                  <ArrowRight aria-hidden="true" />
                </Button>
              </div>
            </>
          )}
        </StepSection>

        <StepSection
          n={3}
          title="Datos del informe"
          active={step === 3}
          done={generated}
          summary={generated ? "Informes descargados" : undefined}
          onEdit={selectedStudents.size > 0 && !stale ? () => setStep(3) : undefined}
        >
          <ReportDataForm
            ficha={ficha}
            coordinatorName={coordinatorName}
            onCoordinatorChange={setCoordinatorName}
            reportDate={reportDate}
            onReportDateChange={setReportDate}
            onError={setError}
          />
          <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
            <span className="text-sm text-muted-foreground">
              {generated
                ? "Se descargó el .zip con un informe por aprendiz."
                : `Un informe Word por aprendiz: ${selectedStudents.size}.`}
            </span>
            <Button onClick={handleGenerate} disabled={generating || selectedStudents.size === 0 || !instructorName}>
              {generating ? <Loader2 aria-hidden="true" className="animate-spin" /> : <Download aria-hidden="true" />}
              {generating ? "Generando" : `Generar ${selectedStudents.size === 1 ? "1 informe" : `${selectedStudents.size} informes`}`}
            </Button>
          </div>
        </StepSection>
      </div>

      <EvidencePicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        evidences={evidences}
        selected={validEvidences}
        onChange={setSelectedEvidences}
        cutoffs={cutoffs}
        title="Evidencias a evaluar"
      />
    </>
  );
}
