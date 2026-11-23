"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { clearReadCache, fetchScraperStatus } from "@/lib/api";
import {
  RefreshCw,
  X,
  AlertCircle,
  Circle,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import type { ScraperStatus, ScraperStep } from "@/types/api";

// --- Context for sharing state between SyncButton and SyncProgress ---

interface SyncProgressContextValue {
  isRunning: boolean;
  /**
   * Empieza a seguir un job de sincronización.
   * @param jobId id del job lanzado por ESTA pestaña; null = adoptar el job
   *   en curso (tras un 409 o al montar con un job ya corriendo).
   */
  start: (onComplete?: () => void, jobId?: string | null) => void;
}

const SyncProgressContext = createContext<SyncProgressContextValue>({
  isRunning: false,
  start: () => {},
});

export function useSyncProgress() {
  return useContext(SyncProgressContext);
}

// --- Provider wraps the app ---

export function SyncProgressProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [status, setStatus] = useState<ScraperStatus | null>(null);
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  // Job superpuesto: nuestro job terminó y otro (p. ej. de otra pestaña) corre ahora
  const [superseded, setSuperseded] = useState(false);
  const onCompleteRef = useRef<(() => void) | undefined>(undefined);
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  // Job que ESTA pestaña sigue; null = adoptar el primero que veamos
  const trackedJobIdRef = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = undefined;
    }
  }, []);

  const poll = useCallback(async () => {
    try {
      const data = await fetchScraperStatus();

      // Adoptar el job si empezamos sin id (409 o job ya corriendo al montar)
      if (trackedJobIdRef.current === null && data.job_id) {
        trackedJobIdRef.current = data.job_id;
      }

      // El status global ya es de OTRO job (otra pestaña lanzó uno nuevo):
      // nuestro job terminó — no pintar el progreso ajeno como propio.
      if (
        trackedJobIdRef.current &&
        data.job_id &&
        data.job_id !== trackedJobIdRef.current
      ) {
        stopPolling();
        setSuperseded(true);
        return;
      }

      setStatus(data);

      if (data.status === "completed" || data.status === "failed") {
        // Hay datos nuevos en el servidor: invalidar el caché de lecturas
        clearReadCache();
        stopPolling();
        if (data.status === "completed" && onCompleteRef.current) {
          // Small delay to let the user see "completed" before refresh
          setTimeout(() => onCompleteRef.current?.(), 2000);
        }
        // Auto-dismiss after 8s
        setTimeout(() => setVisible(false), 8000);
      }
    } catch {
      // API unreachable, keep polling
    }
  }, [stopPolling]);

  const start = useCallback(
    (onComplete?: () => void, jobId: string | null = null) => {
      onCompleteRef.current = onComplete;
      trackedJobIdRef.current = jobId;
      setSuperseded(false);
      setDismissed(false);
      setVisible(true);
      setStartedAt(Date.now());

      // Start polling
      poll();
      pollRef.current = setInterval(poll, 2000);
    },
    [poll],
  );

  // Cleanup on unmount
  useEffect(() => stopPolling, [stopPolling]);

  // Check on mount if there's already a running job
  useEffect(() => {
    fetchScraperStatus()
      .then((data) => {
        if (data.status === "running") {
          setStatus(data);
          start();
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isRunning = status?.status === "running";

  const contextValue = useMemo(
    () => ({ isRunning, start }),
    [isRunning, start],
  );

  return (
    <SyncProgressContext.Provider value={contextValue}>
      {children}
      {visible && !dismissed && superseded && (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
          <div className="w-80 rounded-lg border border-info-border bg-popover/95 p-4 text-popover-foreground shadow-lg backdrop-blur-sm">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-info-fg" />
                <div>
                  <p className="text-sm font-semibold">Sincronización finalizada</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Tu sincronización terminó y ahora hay otra en curso
                    (posiblemente iniciada en otra pestaña). Recarga para ver
                    los datos actualizados.
                  </p>
                  <button
                    onClick={() => window.location.reload()}
                    className="mt-2 cursor-pointer rounded-lg bg-primary px-3 py-1 text-xs font-medium text-primary-foreground transition-colors duration-150 ease-out hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Recargar
                  </button>
                </div>
              </div>
              <button
                onClick={() => setDismissed(true)}
                aria-label="Cerrar notificación"
                className="cursor-pointer rounded p-0.5 text-muted-foreground transition-colors duration-150 ease-out hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X aria-hidden="true" className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
      {visible && !dismissed && !superseded && status && status.status !== "idle" && (
        <SyncToast
          status={status}
          startedAt={startedAt}
          onDismiss={() => setDismissed(true)}
        />
      )}
    </SyncProgressContext.Provider>
  );
}

// --- Toast component ---

function SyncToast({
  status,
  startedAt,
  onDismiss,
}: {
  status: ScraperStatus;
  startedAt: number;
  onDismiss: () => void;
}) {
  const isCompleted = status.status === "completed";
  const isFailed = status.status === "failed";
  const isRunning = status.status === "running";

  // Timer de tiempo transcurrido local al toast: el tick de 1s solo
  // re-renderiza este componente, no el provider ni su subtree.
  const [elapsed, setElapsed] = useState(() =>
    Math.max(0, Math.floor((Date.now() - startedAt) / 1000)),
  );
  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    }, 1000);
    return () => clearInterval(id);
  }, [isRunning, startedAt]);

  const progress =
    status.courses_total > 0
      ? (status.courses_done / status.courses_total) * 100
      : 0;

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
      <div
        className={`w-80 rounded-lg border bg-popover/95 text-popover-foreground shadow-lg backdrop-blur-sm ${
          isFailed
            ? "border-danger-border"
            : isCompleted
              ? "border-ok-border"
              : "border-border"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-3 pb-2">
          <div className="flex items-center gap-2">
            {isRunning && (
              <RefreshCw className="h-4 w-4 animate-spin text-primary" />
            )}
            {isCompleted && (
              <CheckCircle2 className="h-4 w-4 text-ok-fg" />
            )}
            {isFailed && <AlertCircle className="h-4 w-4 text-danger-fg" />}
            <span className="text-sm font-semibold">
              {isRunning && "Sincronizando Zajuna"}
              {isCompleted && "Sincronizacion completada"}
              {isFailed && "Error de sincronizacion"}
            </span>
          </div>
          <button
            onClick={onDismiss}
            aria-label="Cerrar notificación"
            className="cursor-pointer rounded p-0.5 text-muted-foreground transition-colors duration-150 ease-out hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X aria-hidden="true" className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Steps */}
        {status.steps.length > 0 && (
          <div className="max-h-48 space-y-0.5 overflow-y-auto px-4 py-1">
            {status.steps.map((step, i) => (
              <StepRow key={i} step={step} />
            ))}
          </div>
        )}

        {/* Progress bar */}
        {isRunning && (
          <div className="px-4 pt-2">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
                style={{ width: `${Math.max(progress, 5)}%` }}
              />
            </div>
            <div className="mt-1 flex items-center justify-between text-[10px] tabular-nums text-muted-foreground">
              <span>
                {status.courses_done}/{status.courses_total} fichas
              </span>
              <span>{formatElapsed(elapsed)}</span>
            </div>
          </div>
        )}

        {/* Completed summary */}
        {isCompleted && status.duration_seconds && (
          <div className="px-4 pt-1">
            <p className="text-xs tabular-nums text-ok-fg">
              Completado en {status.duration_seconds.toFixed(0)}s
            </p>
          </div>
        )}

        {/* Error message */}
        {isFailed && status.error && (
          <div className="px-4 pt-1">
            <p className="text-xs text-danger-fg">{status.error}</p>
          </div>
        )}

        {/* Bottom padding */}
        <div className="h-3" />
      </div>
    </div>
  );
}

function StepRow({ step }: { step: ScraperStep }) {
  return (
    <div className="flex items-center gap-2 py-0.5">
      <StepIcon status={step.status} />
      <span
        className={`text-xs ${
          step.status === "completed"
            ? "text-muted-foreground"
            : step.status === "running"
              ? "font-medium text-foreground"
              : step.status === "failed"
                ? "text-danger-fg"
                : "text-muted-foreground/50"
        }`}
      >
        {step.label}
      </span>
    </div>
  );
}

function StepIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-ok-fg" />;
    case "running":
      return <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />;
    case "failed":
      return <AlertCircle className="h-3.5 w-3.5 shrink-0 text-danger-fg" />;
    default:
      return <Circle className="h-3.5 w-3.5 shrink-0 text-muted-foreground/30" />;
  }
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}
