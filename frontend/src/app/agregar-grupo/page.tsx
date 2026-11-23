"use client";

/**
 * Agregar grupo — elegir qué cursos de Zajuna monitorea el instructor.
 *
 * 1. Consulta "Mis cursos" en Zajuna con la cuenta conectada (login real, 10-30 s).
 * 2. El instructor marca los grupos a monitorear y guarda la selección.
 * 3. Los grupos nuevos se sincronizan de inmediato; al terminar se recarga
 *    para que aparezcan en el sidebar y el dashboard.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { FolderPlus, Loader2, RefreshCw, KeyRound } from "lucide-react";
import { Topbar } from "@/components/layout/topbar";
import { useSyncProgress } from "@/components/layout/sync-progress";
import { CoursePicker } from "@/components/courses/course-picker";
import {
  discoverCourses,
  fetchFichas,
  fetchTrackedCourses,
  fetchZajunaAccount,
  notifyFichasChanged,
  saveTrackedCourses,
  triggerScraper,
} from "@/lib/api";
import { buildCourseRows, type CourseRow } from "@/lib/course-selection";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Phase = "checking" | "no-account" | "discovering" | "ready" | "error";

function discoverErrorMessage(err: unknown): string {
  const msg = err instanceof Error ? err.message : "";
  if (msg.includes("409")) return "Conecta tu cuenta Zajuna antes de buscar tus grupos.";
  if (msg.includes("400"))
    return "Zajuna rechazó tus credenciales guardadas. Actualízalas en Cuenta Zajuna.";
  return "Zajuna no está respondiendo en este momento. Intenta de nuevo en unos minutos.";
}

export default function AddGroupPage() {
  const { isRunning, start } = useSyncProgress();
  const [phase, setPhase] = useState<Phase>("checking");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [rows, setRows] = useState<CourseRow[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [truncated, setTruncated] = useState(false);
  const [saving, setSaving] = useState(false);

  const discover = useCallback(async () => {
    setPhase("discovering");
    setError(null);
    setSuccess(null);
    try {
      const [found, tracked, fichas] = await Promise.all([
        discoverCourses(),
        fetchTrackedCourses(),
        fetchFichas().catch(() => []),
      ]);
      const built = buildCourseRows(
        found.courses,
        tracked.courses,
        tracked.configured,
        fichas.map((f) => f.ficha)
      );
      setRows(built.rows);
      setSelected(built.selected);
      setTruncated(found.truncated);
      setPhase("ready");
    } catch (err) {
      setError(discoverErrorMessage(err));
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchZajunaAccount()
      .then((acc) => {
        if (cancelled) return;
        if (acc.connected) {
          discover();
        } else {
          setPhase("no-account");
        }
      })
      .catch(() => {
        if (cancelled) return;
        setError("No fue posible consultar el estado de tu cuenta Zajuna.");
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [discover]);

  const toggle = (courseId: number) => {
    setSuccess(null);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(courseId)) next.delete(courseId);
      else next.add(courseId);
      return next;
    });
  };

  const selectedRows = useMemo(
    () => rows.filter((r) => selected.has(r.course_id)),
    [rows, selected]
  );
  const newFichas = selectedRows.filter((r) => !r.tracked).map((r) => r.ficha);
  const removedCount = rows.filter((r) => r.tracked && !selected.has(r.course_id)).length;
  const hasChanges = newFichas.length > 0 || removedCount > 0;
  // Con lista, el resultado de guardar se ve en la barra fija, junto al botón
  const showBar = phase === "ready" && rows.length > 0;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const saved = await saveTrackedCourses(selectedRows);
      const savedIds = new Set(saved.courses.map((c) => c.course_id));
      // La barra lateral y el dashboard dejan de mostrar los grupos quitados
      notifyFichasChanged();
      setRows((prev) =>
        prev
          .map((r) => ({ ...r, tracked: savedIds.has(r.course_id) }))
          .filter((r) => !r.missing || r.tracked)
      );

      if (newFichas.length === 0) {
        setSuccess(
          removedCount > 0
            ? `Listo: ${removedCount === 1 ? "el grupo quitado ya no aparece" : "los grupos quitados ya no aparecen"} en el monitor. Sus datos siguen guardados.`
            : "Selección guardada."
        );
        return;
      }
      try {
        const job = await triggerScraper(newFichas);
        start(() => window.location.reload(), job.job_id);
        setSuccess(
          `Selección guardada. Sincronizando ${newFichas.length === 1 ? "el grupo" : "los grupos"} ${newFichas.join(", ")}…`
        );
      } catch (err) {
        setSuccess(
          err instanceof Error && err.message.includes("409")
            ? "Selección guardada. Hay otra sincronización en curso: cuando termine, usa Sincronizar para traer los grupos nuevos."
            : "Selección guardada, pero no se pudo iniciar la sincronización. Usa Sincronizar más tarde."
        );
      }
    } catch {
      setError("No fue posible guardar la selección. Intenta de nuevo.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Topbar
        title="Agregar grupo"
        description="Estos son los cursos de tu cuenta Zajuna. Marca los grupos que quieres ver en el monitor: los nuevos se sincronizan al guardar. Si quitas uno, se oculta y sus datos se guardan; al agregarlo de nuevo vuelve con sus reportes y seguimiento."
        actions={
          (phase === "ready" || phase === "error") && (
            <Button variant="outline" size="sm" pill onClick={discover}>
              <RefreshCw aria-hidden="true" />
              Volver a consultar
            </Button>
          )
        }
      />
      <div className="max-w-3xl space-y-5 p-4 sm:p-6">

        {error && (
          <div role="alert" className="rounded-xl border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium leading-snug text-danger-fg">
            {error}{" "}
            {error.includes("Cuenta Zajuna") && (
              <Link href="/cuenta-zajuna" className="underline underline-offset-2">
                Ir a Cuenta Zajuna
              </Link>
            )}
          </div>
        )}
        {success && !showBar && (
          <div role="status" className="rounded-xl border border-ok-border bg-ok-soft px-4 py-3 text-sm font-medium leading-snug text-ok-fg">
            {success}
          </div>
        )}

        {phase === "no-account" && <NoAccountState />}
        {(phase === "checking" || phase === "discovering") && (
          <DiscoveringState checking={phase === "checking"} />
        )}

        {phase === "ready" && (
          <section className="overflow-hidden rounded-xl border bg-card shadow-card">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h3 className="text-sm font-semibold text-foreground">Mis cursos en Zajuna</h3>
              <span className="text-xs tabular-nums text-muted-foreground">
                {selected.size} de {rows.filter((r) => r.ficha).length} seleccionados
              </span>
            </div>
            {rows.length > 0 ? (
              <CoursePicker rows={rows} selected={selected} onToggle={toggle} />
            ) : (
              <p className="px-4 py-6 text-sm text-muted-foreground">
                Tu cuenta Zajuna no tiene cursos visibles.
              </p>
            )}
          </section>
        )}

        {phase === "ready" && truncated && (
          <div role="note" className="rounded-xl border border-warn-border bg-warn-soft px-4 py-3 text-xs leading-relaxed text-warn-fg">
            Zajuna solo mostró una parte de tus cursos. Si no ves un grupo,
            ábrelo una vez en Zajuna y vuelve a consultar.
          </div>
        )}

        {/* Barra fija abajo: el resumen y Guardar siguen a la vista en listas largas */}
        {showBar && (
          <div className="sticky bottom-4 z-10 flex flex-col gap-3 rounded-xl border bg-card px-4 py-3 shadow-lg sm:flex-row sm:items-center sm:justify-between">
            <p role="status" className={cn("text-xs leading-relaxed", success && !hasChanges ? "font-medium text-ok-fg" : "text-muted-foreground")}>
              {newFichas.length > 0 && `${newFichas.length} por agregar. `}
              {removedCount > 0 &&
                `${removedCount} se ${removedCount === 1 ? "quitará" : "quitarán"} del monitor. Sus datos se guardan y vuelven si lo agregas de nuevo.`}
              {!hasChanges && (success ?? "Sin cambios por guardar.")}
            </p>
            <Button pill onClick={handleSave} disabled={!hasChanges || saving || isRunning}>
              {saving && <Loader2 aria-hidden="true" className="animate-spin" />}
              {newFichas.length > 0
                ? "Guardar y sincronizar"
                : removedCount > 0
                  ? `Quitar ${removedCount === 1 ? "grupo" : `${removedCount} grupos`}`
                  : "Guardar selección"}
            </Button>
          </div>
        )}
      </div>
    </>
  );
}

function DiscoveringState({ checking }: { checking: boolean }) {
  return (
    <section className="flex items-center gap-3 rounded-xl border bg-card shadow-card px-4 py-6" aria-live="polite">
      <Loader2 aria-hidden="true" className="h-5 w-5 shrink-0 animate-spin text-sena-green-dark dark:text-sena-green" />
      <div>
        <p className="text-sm font-semibold text-foreground">
          {checking ? "Revisando tu cuenta…" : "Consultando tus cursos en Zajuna…"}
        </p>
        {!checking && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            Iniciamos sesión en Zajuna con tu cuenta; toma entre 10 y 30 segundos.
          </p>
        )}
      </div>
    </section>
  );
}

function NoAccountState() {
  return (
    <section className="flex flex-col items-center rounded-xl border bg-card shadow-card px-6 py-10 text-center">
      <FolderPlus aria-hidden="true" className="h-8 w-8 text-muted-foreground" />
      <h3 className="mt-3 text-sm font-semibold text-foreground">Primero conecta tu cuenta Zajuna</h3>
      <p className="mt-1 max-w-[48ch] text-sm text-muted-foreground">
        Usamos tu cuenta para listar los cursos en los que eres instructor.
      </p>
      <Link href="/cuenta-zajuna" className={cn(buttonVariants({ pill: true }), "mt-4")}>
        <KeyRound aria-hidden="true" className="h-4 w-4" />
        Conectar cuenta Zajuna
      </Link>
    </section>
  );
}
