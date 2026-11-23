"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, AlertCircle, Loader2, FolderOpen } from "lucide-react";
import { fetchDownloadStatus } from "@/lib/api";
import type { DownloadStatusResponse } from "@/types/api";

interface DownloadProgressProps {
  ficha: string;
  jobId: string;
  onComplete: (folderPath?: string) => void;
}

export function DownloadProgress({
  ficha,
  jobId,
  onComplete,
}: DownloadProgressProps) {
  const [status, setStatus] = useState<DownloadStatusResponse | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await fetchDownloadStatus(ficha, jobId);
        setStatus(data);
        if (data.status === "completed" || data.status === "failed") {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          onComplete(data.folder_path ?? undefined);
        }
      } catch {
        // Ignore polling errors
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 1500);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [ficha, jobId, onComplete]);

  if (!status) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Iniciando descarga...
      </div>
    );
  }

  const percentage =
    status.total_files > 0
      ? Math.round((status.downloaded / status.total_files) * 100)
      : 0;

  const isRunning = status.status === "running";
  const isCompleted = status.status === "completed";
  const isFailed = status.status === "failed";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        {isRunning && <Loader2 className="h-5 w-5 animate-spin text-primary" />}
        {isCompleted && (
          <CheckCircle2 className="h-5 w-5 text-ok-fg" />
        )}
        {isFailed && <AlertCircle className="h-5 w-5 text-danger-fg" />}
        <span className="text-sm font-semibold text-foreground">
          {isRunning && "Descargando archivos..."}
          {isCompleted && "Descarga completada"}
          {isFailed && "Error en la descarga"}
        </span>
        <span className="ml-auto text-sm font-semibold tabular-nums text-foreground">
          {status.downloaded}
          <span className="font-normal text-muted-foreground">
            {" "}/ {status.total_files}
          </span>
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            isFailed ? "bg-danger" : isCompleted ? "bg-ok" : "bg-primary"
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Current file */}
      {isRunning && status.current_file && (
        <p className="truncate text-sm text-muted-foreground">
          Descargando: {status.current_file}
        </p>
      )}

      {/* Folder path */}
      {status.folder_path && (isCompleted || isRunning) && (
        <div className="flex items-start gap-2 rounded-md border bg-muted/50 p-3 text-sm">
          <FolderOpen
            aria-hidden="true"
            className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
          />
          <div className="min-w-0">
            <p className="font-medium text-foreground">Carpeta de destino</p>
            <p className="break-all font-mono text-xs text-muted-foreground">
              {status.folder_path}
            </p>
          </div>
        </div>
      )}

      {/* Downloaded files */}
      {status.files.length > 0 && (
        <div className="max-h-[200px] overflow-y-auto rounded-md border p-2 text-xs">
          {status.files.map((f, i) => (
            <div key={i} className="flex items-center gap-1.5 py-0.5">
              <CheckCircle2 className="h-3 w-3 shrink-0 text-ok-fg" />
              <span className="truncate">{f}</span>
            </div>
          ))}
        </div>
      )}

      {/* Errors */}
      {status.errors.length > 0 && (
        <div className="space-y-1 rounded-md border border-danger-border bg-danger-soft p-3">
          <p className="text-sm font-medium text-danger-fg">
            Errores ({status.errors.length})
          </p>
          {status.errors.map((err, i) => (
            <p key={i} className="text-xs text-danger-fg">
              {err}
            </p>
          ))}
        </div>
      )}

    </div>
  );
}
