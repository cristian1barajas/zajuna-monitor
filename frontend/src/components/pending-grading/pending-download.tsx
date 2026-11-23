"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, ClipboardCopy, Download, FolderOpen, Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fetchPendingDownloadStatus, startPendingDownload } from "@/lib/api";
import type { BatchDownloadStatusResponse, PendingGradingResult } from "@/types/api";

/** Misma clave que Descargar Evidencias: la ruta se comparte entre las dos páginas. */
const DIR_KEY = "zajuna_download_dir";
const DEFAULT_DIR = "C:\\Users\\crist\\Downloads\\Zajuna";
const POLL_MS = 1500;

interface PendingDownloadProps {
  ficha: string;
  /** Tareas con entregas por calificar, en el orden en que se descargan. */
  assignments: PendingGradingResult[];
}

function readSavedDir(): string {
  try {
    return localStorage.getItem(DIR_KEY) || DEFAULT_DIR;
  } catch {
    return DEFAULT_DIR;
  }
}

function gradingPrompt(folder: string): string {
  return (
    "Califica las evidencias de cada subcarpeta de la siguiente carpeta, pero debes leer una por una, " +
    "lees una y generas la calificación en el archivo HTML respectivo, y luego lees la siguiente, " +
    `y generas el siguiente archivo HTML: ${folder}`
  );
}

export function PendingDownload({ ficha, assignments }: PendingDownloadProps) {
  const [targetDir, setTargetDir] = useState(readSavedDir);
  const [includeInstrument, setIncludeInstrument] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<BatchDownloadStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const running = jobId !== null && (status === null || status.status === "pending" || status.status === "running");
  const rootFolder = `${targetDir}\\${ficha}`;
  const files = assignments.reduce((sum, r) => sum + (r.needs_grading ?? 0), 0);

  useEffect(() => {
    try {
      localStorage.setItem(DIR_KEY, targetDir);
    } catch {
      /* sin almacenamiento local: la ruta solo vive en esta visita */
    }
  }, [targetDir]);

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    const poll = async () => {
      try {
        const data = await fetchPendingDownloadStatus(ficha, jobId);
        if (stopped) return;
        setStatus(data);
        if (data.status === "pending" || data.status === "running") {
          setTimeout(poll, POLL_MS);
        }
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : "No se pudo leer el progreso");
      }
    };
    poll();
    return () => {
      stopped = true;
    };
  }, [ficha, jobId]);

  const start = async () => {
    setError(null);
    setStatus(null);
    try {
      const res = await startPendingDownload(ficha, {
        cmids: assignments.map((r) => r.cmid as number),
        target_dir: rootFolder,
        include_instrument: includeInstrument,
      });
      setJobId(res.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo iniciar la descarga");
    }
  };

  const done = status?.status === "completed";
  const pct = status && status.total_files > 0 ? Math.round((status.downloaded / status.total_files) * 100) : 0;

  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-foreground">Descargar lo que debes calificar</h3>
          <p className="text-xs text-muted-foreground">
            {assignments.length} {assignments.length === 1 ? "tarea" : "tareas"} · {files}{" "}
            {files === 1 ? "entrega" : "entregas"} sin calificar. Los foros y cuestionarios no
            tienen archivos.
          </p>
        </div>
        <Button onClick={start} disabled={running || assignments.length === 0 || !targetDir}>
          {running ? (
            <Loader2 aria-hidden="true" className="animate-spin" />
          ) : (
            <Download aria-hidden="true" />
          )}
          {running ? "Descargando" : `Descargar ${files} ${files === 1 ? "entrega" : "entregas"}`}
        </Button>
      </div>

      <div className="space-y-3 p-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <div className="min-w-0">
            <label
              htmlFor="ruta-descarga-pendientes"
              className="mb-1.5 flex items-center gap-1.5 text-[13px] font-medium text-foreground"
            >
              <FolderOpen aria-hidden="true" className="h-4 w-4 text-muted-foreground" />
              Ruta de descarga
            </label>
            <input
              id="ruta-descarga-pendientes"
              type="text"
              value={targetDir}
              disabled={running}
              onChange={(e) => setTargetDir(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-3 font-mono text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out focus:border-sena-green focus:ring-2 focus:ring-ring/30"
            />
          </div>
          <label className="flex h-9 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeInstrument}
              disabled={running}
              onChange={(e) => setIncludeInstrument(e.target.checked)}
              className="rounded"
            />
            Incluir instrumento de evaluación
          </label>
        </div>
        <p className="text-xs text-muted-foreground">
          Cada tarea queda en su propia carpeta dentro de{" "}
          <span className="font-mono font-medium text-foreground">{rootFolder}\</span>
        </p>

        {error && (
          <p role="alert" className="rounded-md border border-danger-border bg-danger-soft px-3 py-2 text-sm text-danger-fg">
            {error}
          </p>
        )}

        {status && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="truncate">
                {done ? "Descarga terminada" : status.current_file ?? "Preparando…"}
              </span>
              <span className="tabular-nums">
                {status.downloaded}/{status.total_files} archivos
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
                style={{ width: `${done ? 100 : pct}%` }}
              />
            </div>
            <ul className="space-y-1">
              {status.items.map((item) => (
                <li key={item.cmid} className="flex items-center gap-2 text-xs">
                  {item.status === "completed" ? (
                    <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-ok-fg" />
                  ) : item.status === "failed" ? (
                    <XCircle aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-danger-fg" />
                  ) : item.status === "running" ? (
                    <Loader2 aria-hidden="true" className="h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground" />
                  ) : (
                    <span aria-hidden="true" className="h-3.5 w-3.5 shrink-0 rounded-full border border-muted-foreground/40" />
                  )}
                  <span className="min-w-0 flex-1 truncate">
                    {item.name ??
                      assignments.find((a) => a.cmid === item.cmid)?.name ??
                      `Tarea ${item.cmid}`}
                  </span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    {item.status === "failed"
                      ? item.errors[0] ?? "Falló"
                      : `${item.downloaded}/${item.total_files}`}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {done && (
          <div className="space-y-2 rounded-lg border border-notice-border bg-notice-soft p-3">
            <p className="text-xs leading-relaxed text-notice-fg">
              Para calificar con Claude Code, copia este mensaje y pégalo allá:
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate rounded bg-notice-border/40 px-2 py-1.5 text-xs text-notice-fg">
                {gradingPrompt(rootFolder)}
              </code>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(gradingPrompt(rootFolder));
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
              >
                <ClipboardCopy aria-hidden="true" />
                {copied ? "Copiado" : "Copiar"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
