"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { RotateCw, Search } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { EvidenceFilters } from "@/components/pending-grading/evidence-filters";
import { PendingDownload } from "@/components/pending-grading/pending-download";
import { PendingTable, type RowState } from "@/components/pending-grading/pending-table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  checkPendingGrading,
  fetchAssignments,
  fetchCronograma,
  fetchFichaDetail,
} from "@/lib/api";
import {
  EMPTY_FILTERS,
  RESULTS_UPDATED_EVENT,
  applyFilters,
  buildCutoffMap,
  compareGuides,
  downloadableResults,
  guideOf,
  needsAction,
  parseFilters,
  resultsStorageKey,
  serializeFilters,
  type PendingFilters,
} from "@/lib/pending-grading";
import { cn } from "@/lib/utils";
import type {
  AssignmentMappingResponse,
  CronogramaResponse,
  FichaDetailResponse,
  PendingGradingResult,
} from "@/types/api";

type View = "pendientes" | "todas";

interface StoredResults {
  checked_at: string;
  results: PendingGradingResult[];
}

function readStorage<T>(key: string, parse: (raw: string | null) => T): T {
  try {
    return parse(localStorage.getItem(key));
  } catch {
    return parse(null);
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* sin almacenamiento local: el estado vive solo en esta visita */
  }
}

function errorResult(itemId: number, name: string | null, message: string): PendingGradingResult {
  return {
    item_id: itemId,
    cmid: null,
    name,
    module_type: "assign",
    participants: null,
    submitted: null,
    needs_grading: null,
    drafts: null,
    total_discussions: null,
    quiz_approved: null,
    quiz_disapproved: null,
    quiz_pending: null,
    pending_students: [],
    error: message,
  };
}

const RETRY_DELAY_MS = 5_000;

/** El error de la petición, en palabras de quien califica. */
function describeError(e: unknown): string {
  const message = e instanceof Error ? e.message : "";
  if (message === "Failed to fetch" || message.includes("NetworkError")) {
    return "Se cortó la conexión con el monitor mientras consultaba. Vuelve a intentarlo.";
  }
  if (message.includes("API error 503")) {
    return "Zajuna no dejó iniciar sesión en este momento. Suele pasar por ratos: reintenta en un minuto.";
  }
  return message || "Error desconocido";
}

/** Consulta una evidencia; si la petición se cae (red o login), la repite una vez. */
async function checkOne(ficha: string, itemId: number): Promise<PendingGradingResult> {
  try {
    return (await checkPendingGrading(ficha, [itemId])).results[0];
  } catch {
    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
    return (await checkPendingGrading(ficha, [itemId])).results[0];
  }
}

export default function PendingGradingPage() {
  const params = useParams();
  const ficha = params.ficha as string;
  // ?q= llega desde Alertas; useSearchParams ve la URL nueva al navegar dentro de la app
  const query = useSearchParams().get("q");
  const selectionKey = `pending-grading-selection-${ficha}`;
  const filtersKey = `pending-grading-filters-${ficha}`;
  const resultsKey = resultsStorageKey(ficha);

  const [data, setData] = useState<FichaDetailResponse | null>(null);
  const [assignments, setAssignments] = useState<AssignmentMappingResponse | null>(null);
  const [cronograma, setCronograma] = useState<CronogramaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ?q= (desde Alertas) abre la página buscando esa evidencia; si no, los filtros guardados
  const [filters, setFilters] = useState<PendingFilters>(() => {
    return query ? { ...EMPTY_FILTERS, text: query } : readStorage(filtersKey, parseFilters);
  });
  const [selected, setSelected] = useState<Set<number>>(() =>
    readStorage(selectionKey, (raw) => new Set<number>(raw ? (JSON.parse(raw) as number[]) : [])),
  );
  const [stored, setStored] = useState<StoredResults | null>(() =>
    readStorage(resultsKey, (raw) => (raw ? (JSON.parse(raw) as StoredResults) : null)),
  );
  const [rowStates, setRowStates] = useState<Map<number, RowState>>(new Map());
  const [batchSize, setBatchSize] = useState(0);
  // Llegando desde una alerta (?q=) se muestra la evidencia aunque no esté consultada
  const [view, setView] = useState<View>(() =>
    !query && stored?.results.some(needsAction) ? "pendientes" : "todas",
  );
  const checking = rowStates.size > 0;

  useEffect(() => {
    fetchFichaDetail(ficha)
      .then(setData)
      .catch((e) => setError(e.message));
    fetchAssignments(ficha)
      .then(setAssignments)
      .catch(() => {}); // Sin mapeo, todo se trata como tarea
    fetchCronograma(ficha)
      .then(setCronograma)
      .catch(() => {}); // El cronograma es opcional: sin él no hay filtro de cierre
  }, [ficha]);

  useEffect(() => writeStorage(filtersKey, serializeFilters(filters)), [filters, filtersKey]);
  useEffect(
    () => writeStorage(selectionKey, selected.size ? JSON.stringify([...selected]) : null),
    [selected, selectionKey],
  );
  useEffect(() => {
    writeStorage(resultsKey, stored ? JSON.stringify(stored) : null);
    // La barra lateral muestra el conteo de esta ficha; avisarle en esta pestaña
    window.dispatchEvent(new Event(RESULTS_UPDATED_EVENT));
  }, [stored, resultsKey]);

  const moduleTypes = useMemo(() => {
    const map = new Map<number, string>();
    for (const a of assignments?.assignments ?? []) {
      if (a.item_id != null) map.set(a.item_id, a.module_type);
    }
    return map;
  }, [assignments]);

  const cutoffs = useMemo(() => buildCutoffMap(cronograma), [cronograma]);
  const results = useMemo(
    () => new Map((stored?.results ?? []).map((r) => [r.item_id, r])),
    [stored],
  );

  const evidences = useMemo(() => data?.evidences ?? [], [data]);
  const guides = useMemo(
    () =>
      [...new Set(evidences.map((e) => guideOf(e.name)).filter((g): g is string => g !== null))].sort(
        compareGuides,
      ),
    [evidences],
  );
  const phases = useMemo(() => [...new Set(evidences.map((e) => e.category))], [evidences]);

  const filtered = useMemo(
    () => applyFilters(evidences, filters, moduleTypes, cutoffs),
    [evidences, filters, moduleTypes, cutoffs],
  );
  const pendingRows = filtered.filter((ev) => {
    const r = results.get(ev.item_id);
    return needsAction(r) || Boolean(r?.error) || rowStates.has(ev.item_id);
  });
  const rows = view === "pendientes" ? pendingRows : filtered;
  const selectedVisible = filtered.filter((ev) => selected.has(ev.item_id)).map((ev) => ev.item_id);

  const consulted = [...results.values()];
  const failedIds = consulted.filter((r) => r.error).map((r) => r.item_id);
  const retryRow = (itemId: number) => handleCheck([itemId], { keepView: true });
  const withPending = consulted.filter(needsAction);
  const toGrade = withPending.reduce((sum, r) => sum + (r.needs_grading ?? 0), 0);
  const downloadable = downloadableResults(results.values());

  const handleToggle = (itemId: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });

  const handleToggleAll = (itemIds: number[], select: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      for (const id of itemIds) {
        if (select) next.add(id);
        else next.delete(id);
      }
      return next;
    });

  const handleCheck = useCallback(
    async (itemIds: number[], { keepView = false }: { keepView?: boolean } = {}) => {
      if (itemIds.length === 0) return;
      const names = new Map(evidences.map((ev) => [ev.item_id, ev.name]));
      setError(null);
      setBatchSize(itemIds.length);
      setRowStates(new Map(itemIds.map((id) => [id, "queued" as const])));

      const fresh: PendingGradingResult[] = [];
      for (const itemId of itemIds) {
        setRowStates((prev) => new Map(prev).set(itemId, "checking"));
        try {
          fresh.push(await checkOne(ficha, itemId));
        } catch (e) {
          fresh.push(errorResult(itemId, names.get(itemId) ?? null, describeError(e)));
        }
        const latest = fresh[fresh.length - 1];
        setStored((prev) => {
          const merged = new Map((prev?.results ?? []).map((r) => [r.item_id, r]));
          merged.set(latest.item_id, latest);
          return { checked_at: new Date().toISOString(), results: [...merged.values()] };
        });
        setRowStates((prev) => {
          const next = new Map(prev);
          next.delete(itemId);
          return next;
        });
      }
      if (!keepView) setView(fresh.some(needsAction) ? "pendientes" : "todas");
    },
    [evidences, ficha],
  );

  if (error && !data) {
    return (
      <>
        <Topbar title="Por calificar" />
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
        <Topbar title="Por calificar" />
        <div className="space-y-4 p-6">
          <Skeleton className="h-40 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </>
    );
  }

  const hiddenCount = filtered.length - pendingRows.length;

  return (
    <>
      <Topbar
        title="Por calificar"
        description="Filtra, marca las evidencias y consulta en Zajuna qué entregas siguen sin nota. Cada tarea tarda unos segundos; los foros, algo más."
        actions={
          stored && (
            <p className="text-xs tabular-nums text-muted-foreground">
              Última consulta:{" "}
              {new Date(stored.checked_at).toLocaleString("es-CO", {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </p>
          )
        }
      />
      <div className="space-y-5 overflow-hidden p-4 sm:p-6">

        {error && (
          <div
            role="alert"
            className="rounded-md border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium text-danger-fg"
          >
            {error}
          </div>
        )}

        <section className="space-y-4 rounded-xl border bg-card p-4 shadow-card">
          <EvidenceFilters
            filters={filters}
            onChange={setFilters}
            onClear={() => setFilters(EMPTY_FILTERS)}
            guides={guides}
            phases={phases}
            hasCronograma={cutoffs.size > 0}
          />
          <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
            <p className="text-sm text-muted-foreground">
              <span className="font-semibold tabular-nums text-foreground">{selectedVisible.length}</span>{" "}
              de <span className="tabular-nums">{filtered.length}</span> evidencias visibles
              seleccionadas
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {failedIds.length > 0 && !checking && (
                <Button variant="outline" onClick={() => handleCheck(failedIds, { keepView: true })}>
                  <RotateCw aria-hidden="true" />
                  {failedIds.length === 1 ? "Reintentar la fallida" : `Reintentar las ${failedIds.length} fallidas`}
                </Button>
              )}
              <Button
                onClick={() => handleCheck(selectedVisible)}
                disabled={checking || selectedVisible.length === 0}
              >
                <Search aria-hidden="true" />
                {checking
                  ? `Consultando ${batchSize - rowStates.size + 1} de ${batchSize}`
                  : `Consultar ${selectedVisible.length}`}
              </Button>
            </div>
          </div>
        </section>

        {consulted.length > 0 && (
          <dl className="grid grid-cols-3 divide-x overflow-hidden rounded-xl border bg-card shadow-card">
            <div className="px-4 py-3">
              <dt className="text-xs text-muted-foreground">Consultadas</dt>
              <dd className="mt-1 text-2xl font-bold tabular-nums tracking-tight">{consulted.length}</dd>
            </div>
            <div className="px-4 py-3">
              <dt className="text-xs text-muted-foreground">Evidencias con pendientes</dt>
              <dd className="mt-1 text-2xl font-bold tabular-nums tracking-tight">{withPending.length}</dd>
            </div>
            <div className="px-4 py-3">
              <dt className="text-xs text-muted-foreground">Entregas por calificar</dt>
              <dd
                className={cn(
                  "mt-1 text-2xl font-bold tabular-nums tracking-tight",
                  toGrade > 0 ? "text-danger-fg" : "text-ok-fg",
                )}
              >
                {toGrade}
              </dd>
            </div>
          </dl>
        )}

        {downloadable.length > 0 && !checking && (
          <PendingDownload ficha={ficha} assignments={downloadable} />
        )}

        <section className="overflow-hidden rounded-xl border bg-card shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <div role="radiogroup" aria-label="Qué mostrar" className="inline-flex rounded-full border p-0.5">
              {(
                [
                  ["pendientes", `Por calificar (${pendingRows.length})`],
                  ["todas", `Todas (${filtered.length})`],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={view === value}
                  onClick={() => setView(value)}
                  className={cn(
                    "h-7 rounded-full px-3 text-xs font-medium transition-colors duration-150 ease-out",
                    view === value
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            {view === "pendientes" && hiddenCount > 0 && (
              <button
                type="button"
                onClick={() => setView("todas")}
                className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                {hiddenCount} sin pendientes o sin consultar ocultas · Mostrar
              </button>
            )}
          </div>
          <PendingTable
            ficha={ficha}
            rows={rows}
            selected={selected}
            onToggle={handleToggle}
            onToggleAll={handleToggleAll}
            results={results}
            rowStates={rowStates}
            moduleTypes={moduleTypes}
            cutoffs={cutoffs}
            disabled={checking}
            onRetry={retryRow}
            emptyMessage={
              view === "pendientes"
                ? consulted.length > 0
                  ? "Nada por calificar en lo consultado"
                  : "Consulta evidencias para ver aquí lo que debes calificar"
                : "Ninguna evidencia coincide con los filtros"
            }
          />
        </section>
      </div>
    </>
  );
}
