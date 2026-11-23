"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { OutlookConnection } from "@/components/due-process/soportes/outlook-connection";
import { LlamadosFilters } from "@/components/due-process/soportes/llamados-filters";
import {
  LlamadosResults,
  type MissingLlamado,
  type PrintProgress,
} from "@/components/due-process/soportes/llamados-results";
import { ResultsPlaceholder } from "@/components/due-process/soportes/results-placeholder";
import { ActasPanel } from "@/components/due-process/soportes/actas-panel";
import { saveFile } from "@/components/due-process/soportes/save-file";
import {
  SOPORTE_STAGES,
  foldName,
  sendDatesFromRecords,
} from "@/components/due-process/soportes/stages";
import {
  disconnectOutlookSession,
  fetchDueProcess,
  fetchOutlookSession,
  printLlamadosZips,
  searchLlamados,
  startOutlookSession,
} from "@/lib/api";
import type {
  BuscarLlamadosResponse,
  DueProcessRecord,
  OutlookSessionStatus,
  SoporteRegistro,
} from "@/types/api";

const POLL_MS = 2000;

function toggle<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

interface SearchState {
  response: BuscarLlamadosResponse;
  fechas: string[];
  etapas: string[];
}

export default function SoportesLlamadosPage() {
  const params = useParams();
  const ficha = params.ficha as string;

  const [session, setSession] = useState<OutlookSessionStatus | null>(null);
  const [sessionBusy, setSessionBusy] = useState(false);
  const [records, setRecords] = useState<DueProcessRecord[]>([]);
  const [extraDates, setExtraDates] = useState<string[]>([]);
  const [selectedDates, setSelectedDates] = useState<Set<string>>(new Set());
  const [selectedStages, setSelectedStages] = useState<Set<string>>(
    new Set(SOPORTE_STAGES.map((s) => s.key))
  );
  const [search, setSearch] = useState<SearchState | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searching, setSearching] = useState(false);
  const [progress, setProgress] = useState<PrintProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Registro de PDF ya descargados (por id de correo) y aviso para recargarlo.
  const [soportes, setSoportes] = useState<SoporteRegistro[]>([]);
  const [soportesKey, setSoportesKey] = useState(0);
  const descargados = useMemo(
    () => new Map(soportes.map((s) => [s.message_id, s])),
    [soportes]
  );

  const sendDates = useMemo(() => sendDatesFromRecords(records), [records]);
  const connected = session?.status === "connected";

  useEffect(() => {
    fetchOutlookSession()
      .then(setSession)
      .catch((e: Error) => setError(e.message));
    fetchDueProcess(ficha)
      .then((dp) => {
        setRecords(dp.records);
        // Por defecto, los envíos del mes más reciente con llamados.
        const dates = sendDatesFromRecords(dp.records);
        const month = dates[0]?.date.slice(0, 7);
        setSelectedDates(
          new Set(
            dates
              .filter((d) => d.date.startsWith(month ?? ""))
              .map((d) => d.date)
          )
        );
      })
      .catch((e: Error) => setError(e.message));
  }, [ficha]);

  // Mientras Chrome espera el inicio de sesión, se consulta el estado.
  useEffect(() => {
    if (session?.status !== "waiting_login") return;
    const id = window.setInterval(() => {
      fetchOutlookSession()
        .then(setSession)
        .catch(() => undefined);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [session?.status]);

  const runSession = useCallback(
    async (action: () => Promise<OutlookSessionStatus>) => {
      setSessionBusy(true);
      setError(null);
      try {
        setSession(await action());
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setSessionBusy(false);
      }
    },
    []
  );

  const onSearch = async () => {
    setSearching(true);
    setError(null);
    const fechas = [...selectedDates].sort();
    const etapas = SOPORTE_STAGES.map((s) => s.key as string).filter((k) =>
      selectedStages.has(k)
    );
    try {
      const response = await searchLlamados(ficha, fechas, etapas);
      setSearch({ response, fechas, etapas });
      setSelectedIds(new Set(response.correos.map((c) => c.id)));
    } catch (e) {
      setError((e as Error).message);
      fetchOutlookSession()
        .then(setSession)
        .catch(() => undefined);
    } finally {
      setSearching(false);
    }
  };

  const onDownload = async () => {
    if (!search) return;
    const ids = search.response.correos
      .map((c) => c.id)
      .filter((id) => selectedIds.has(id));
    setProgress({ done: 0, total: ids.length });
    setError(null);
    try {
      const files = await printLlamadosZips(ficha, ids, (job) =>
        setProgress({ done: job.done, total: job.total })
      );
      // Un ZIP por día; una pausa corta entre descargas para que el navegador no las agrupe.
      for (const [i, { blob, filename }] of files.entries()) {
        if (i > 0) await new Promise((resolve) => setTimeout(resolve, 400));
        saveFile(blob, filename);
      }
      setSoportesKey((k) => k + 1);
    } catch (e) {
      setError((e as Error).message);
      fetchOutlookSession()
        .then(setSession)
        .catch(() => undefined);
    } finally {
      setProgress(null);
    }
  };

  // Registrados en la app (esas fechas y etapas) sin correo encontrado: posible envío fallido o con otro asunto.
  const missing = useMemo<MissingLlamado[]>(() => {
    if (!search) return [];
    const found = new Set(
      search.response.correos.map(
        (c) => `${foldName(c.student_name)}|${c.stage}`
      )
    );
    const out: MissingLlamado[] = [];
    for (const r of records) {
      for (const h of r.history) {
        const date = h.date.slice(0, 10);
        if (!search.fechas.includes(date) || !search.etapas.includes(h.stage))
          continue;
        if (!found.has(`${foldName(r.full_name)}|${h.stage}`))
          out.push({ name: r.full_name, stage: h.stage, date });
      }
    }
    return out.sort((a, b) => a.name.localeCompare(b.name));
  }, [search, records]);

  return (
    <>
      <Topbar
        title="Soportes de Outlook"
        description="Descarga en PDF los llamados que enviaste desde tu correo SENA, agrupados por etapa, para subirlos a Zajuna."
      />
      <div className="space-y-4 p-4 sm:p-6">
        {error && (
          <div
            role="alert"
            className="rounded-lg border border-danger-border bg-danger-soft p-3 text-sm text-danger-fg"
          >
            {error}
          </div>
        )}
        <OutlookConnection
          session={session}
          busy={sessionBusy}
          onConnect={() => runSession(startOutlookSession)}
          onDisconnect={() => {
            setSearch(null);
            runSession(disconnectOutlookSession);
          }}
        />
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(300px,360px)_minmax(0,1fr)]">
          <div className="lg:sticky lg:top-20">
            <LlamadosFilters
              sendDates={sendDates}
              extraDates={extraDates.filter(
                (d) => !sendDates.some((s) => s.date === d)
              )}
              selectedDates={selectedDates}
              selectedStages={selectedStages}
              canSearch={connected}
              searching={searching}
              onToggleDate={(d) => setSelectedDates((s) => toggle(s, d))}
              onAddDate={(d) => {
                setExtraDates((list) =>
                  list.includes(d) ? list : [...list, d].sort().reverse()
                );
                setSelectedDates((s) => new Set(s).add(d));
              }}
              onRemoveExtraDate={(d) => {
                setExtraDates((list) => list.filter((x) => x !== d));
                setSelectedDates((s) => {
                  const next = new Set(s);
                  next.delete(d);
                  return next;
                });
              }}
              onToggleStage={(stage) =>
                setSelectedStages((s) => toggle(s, stage))
              }
              onSearch={onSearch}
            />
          </div>
          {search && !searching ? (
            <LlamadosResults
              correos={search.response.correos}
              revisados={search.response.revisados}
              missing={missing}
              selected={selectedIds}
              descargados={descargados}
              progress={progress}
              onToggle={(id) => setSelectedIds((s) => toggle(s, id))}
              onToggleStage={(stage, checked) =>
                setSelectedIds((s) => {
                  const next = new Set(s);
                  for (const c of search.response.correos) {
                    if (c.stage !== stage) continue;
                    if (checked) next.add(c.id);
                    else next.delete(c.id);
                  }
                  return next;
                })
              }
              onDownload={onDownload}
            />
          ) : (
            <ResultsPlaceholder
              step={connected ? 1 : 0}
              searching={searching}
            />
          )}
        </div>
        <ActasPanel
          ficha={ficha}
          refreshKey={soportesKey}
          onSoportes={setSoportes}
        />
      </div>
    </>
  );
}
