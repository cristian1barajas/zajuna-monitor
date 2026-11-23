"use client";

import {
  AlertTriangle,
  Download,
  FileCheck2,
  FolderArchive,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { CorreoLlamado, SoporteRegistro } from "@/types/api";
import { SOPORTE_STAGES, formatDay, stageInfo } from "./stages";

export interface MissingLlamado {
  name: string;
  stage: string;
  date: string;
}

/** Avance de la impresión con Outlook; `null` cuando no se está imprimiendo. */
export interface PrintProgress {
  done: number;
  total: number;
}

interface LlamadosResultsProps {
  correos: CorreoLlamado[];
  revisados: number;
  missing: MissingLlamado[];
  selected: Set<string>;
  /** Correos con PDF ya descargado (registro de soportes), por id. */
  descargados: Map<string, SoporteRegistro>;
  progress: PrintProgress | null;
  onToggle: (id: string) => void;
  onToggleStage: (stage: string, checked: boolean) => void;
  onDownload: () => void;
}

function formatSent(iso: string): { day: string; hour: string } {
  const d = new Date(iso);
  return {
    day: d.toLocaleDateString("es-CO", {
      weekday: "short",
      day: "numeric",
      month: "short",
    }),
    hour: d.toLocaleTimeString("es-CO", { hour: "numeric", minute: "2-digit" }),
  };
}

/** Correos encontrados por etapa, selección y descarga del ZIP (impreso por Outlook). */
export function LlamadosResults({
  correos,
  revisados,
  missing,
  selected,
  descargados,
  progress,
  onToggle,
  onToggleStage,
  onDownload,
}: LlamadosResultsProps) {
  const groups = SOPORTE_STAGES.map((s) => ({
    ...s,
    items: correos.filter((c) => c.stage === s.key),
  })).filter((g) => g.items.length > 0);
  const printing = progress !== null;
  // Sale un ZIP por cada día de envío entre los correos elegidos.
  const zipCount = new Set(
    correos.filter((c) => selected.has(c.id)).map((c) => c.sent_date)
  ).size;
  const pct =
    progress && progress.total
      ? Math.round((progress.done / progress.total) * 100)
      : 0;

  return (
    <section
      aria-labelledby="resultados-titulo"
      className="flex min-w-0 flex-col rounded-xl border bg-card shadow-card"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b px-4 py-3">
        <h2 id="resultados-titulo" className="text-sm font-semibold">
          Correos encontrados
        </h2>
        <span
          className="text-xs tabular-nums text-muted-foreground"
          aria-live="polite"
        >
          {correos.length} llamados de este grupo · {revisados} enviados
          revisados
        </span>
      </div>

      {groups.length > 0 && (
        <div
          role="group"
          aria-label="Selección por etapa"
          className="grid grid-cols-2 border-b sm:grid-cols-3 xl:grid-cols-5"
        >
          {groups.map((g) => {
            const chosen = g.items.filter((c) => selected.has(c.id)).length;
            const all = chosen === g.items.length;
            return (
              <button
                key={g.key}
                type="button"
                aria-pressed={all}
                disabled={printing}
                onClick={() => onToggleStage(g.key, !all)}
                title={all ? "Quitar toda la etapa" : "Incluir toda la etapa"}
                className="border-b border-r px-4 py-2.5 text-left transition-colors duration-150 ease-out last:border-r-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring disabled:pointer-events-none sm:border-b-0"
              >
                <span className="block text-xs text-muted-foreground">
                  {g.short}
                </span>
                <span className="mt-0.5 flex items-baseline gap-1">
                  <span
                    className={cn(
                      "text-2xl font-bold tabular-nums tracking-tight",
                      g.tone
                    )}
                  >
                    {chosen}
                  </span>
                  {chosen !== g.items.length && (
                    <span className="text-xs tabular-nums text-muted-foreground">
                      de {g.items.length}
                    </span>
                  )}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {missing.length > 0 && (
        <details className="group border-b bg-warn-soft px-4 py-2.5 text-sm text-warn-fg">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 font-medium">
            <AlertTriangle aria-hidden="true" className="h-4 w-4 shrink-0" />
            {missing.length} registrados en Debido proceso sin correo en Outlook
            esos días
            <span className="ml-auto text-xs font-normal underline group-open:hidden">
              Ver
            </span>
          </summary>
          <ul className="mt-1.5 grid gap-x-6 gap-y-0.5 pl-6 sm:grid-cols-2">
            {missing.map((m) => (
              <li key={`${m.date}-${m.stage}-${m.name}`} className="list-disc">
                {m.name} · {stageInfo(m.stage)?.short ?? m.stage} ·{" "}
                <span className="capitalize">{formatDay(m.date)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {groups.length === 0 ? (
        <p className="m-4 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          No hay llamados de este grupo en esas fechas. Revisa las fechas o las
          etapas.
        </p>
      ) : (
        <div className="max-h-[calc(100vh-22rem)] min-h-64 overflow-auto">
          <table className="w-full min-w-[640px] text-sm">
            <caption className="sr-only">
              Correos de llamados encontrados
            </caption>
            <thead className="sticky top-0 z-10 bg-table-head text-left text-xs font-semibold text-muted-foreground">
              <tr>
                <th scope="col" className="w-10 px-4 py-2">
                  <span className="sr-only">Incluir</span>
                </th>
                <th scope="col" className="px-2 py-2">
                  Aprendiz
                </th>
                <th scope="col" className="px-2 py-2">
                  Enviado a
                </th>
                <th scope="col" className="px-4 py-2 text-right">
                  Enviado
                </th>
              </tr>
            </thead>
            {groups.map((g) => {
              const chosen = g.items.filter((c) => selected.has(c.id)).length;
              return (
                <tbody
                  key={g.key}
                  className="divide-y border-b last:border-b-0"
                >
                  <tr className="bg-muted/30">
                    <td className="px-4 py-1.5">
                      <Checkbox
                        aria-label={`Incluir toda la etapa ${g.label}`}
                        disabled={printing}
                        checked={
                          chosen === g.items.length
                            ? true
                            : chosen > 0
                              ? "indeterminate"
                              : false
                        }
                        onCheckedChange={(v) =>
                          onToggleStage(g.key, v === true)
                        }
                      />
                    </td>
                    <th
                      scope="colgroup"
                      colSpan={3}
                      className="px-2 py-1.5 text-left text-xs font-semibold"
                    >
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          aria-hidden="true"
                          className={cn("h-2 w-2 rounded-full", g.dot)}
                        />
                        {g.label}
                        <span className="font-normal text-muted-foreground">
                          · carpeta{" "}
                          {SOPORTE_STAGES.findIndex((s) => s.key === g.key) + 1}
                        </span>
                      </span>
                    </th>
                  </tr>
                  {g.items.map((c) => {
                    const sent = formatSent(c.sent_at);
                    const on = selected.has(c.id);
                    return (
                      <tr
                        key={c.id}
                        onClick={() => !printing && onToggle(c.id)}
                        className={cn(
                          "cursor-pointer transition-colors duration-150 hover:bg-accent/40",
                          !on && "text-muted-foreground"
                        )}
                      >
                        <td
                          className="px-4 py-2"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Checkbox
                            aria-label={`Incluir a ${c.student_name || c.subject}`}
                            disabled={printing}
                            checked={on}
                            onCheckedChange={() => onToggle(c.id)}
                          />
                        </td>
                        <td className="max-w-0 px-2 py-2">
                          <span className="flex min-w-0 items-center gap-2">
                            <span className="truncate font-medium">
                              {c.student_name || c.subject}
                            </span>
                            {descargados.has(c.id) && (
                              <span
                                className="inline-flex shrink-0 items-center gap-1 rounded-full bg-ok-soft px-1.5 py-0.5 text-[10px] font-medium text-ok-fg"
                                title={`PDF descargado en ${descargados.get(c.id)?.zip}`}
                              >
                                <FileCheck2
                                  aria-hidden="true"
                                  className="h-3 w-3"
                                />
                                PDF
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="max-w-0 px-2 py-2">
                          <span className="block truncate text-xs">
                            {c.to.join(", ")}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-2 text-right text-xs tabular-nums">
                          <span className="capitalize">{sent.day}</span> ·{" "}
                          {sent.hour}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              );
            })}
          </table>
        </div>
      )}

      <div className="mt-auto border-t bg-card px-4 py-3">
        {printing && progress ? (
          <div aria-live="polite">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-2 font-medium">
                <Loader2
                  aria-hidden="true"
                  className="h-4 w-4 animate-spin text-primary"
                />
                Imprimiendo con Outlook {progress.done} de {progress.total}
              </span>
              <span className="text-xs tabular-nums text-muted-foreground">
                {pct} %
              </span>
            </div>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={progress.total}
              aria-valuenow={progress.done}
              aria-label="Correos impresos"
              className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"
            >
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">
              Unos 5 segundos por correo. No cierres la ventana de Chrome de
              Outlook.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="flex items-start gap-2 text-xs text-muted-foreground">
              <FolderArchive
                aria-hidden="true"
                className="mt-0.5 h-4 w-4 shrink-0"
              />
              <span>
                Un ZIP por día de envío; en cada uno, un PDF por correo impreso
                con la opción Imprimir de Outlook, en una carpeta por etapa.
              </span>
            </p>
            <Button
              onClick={onDownload}
              disabled={selected.size === 0}
              className="shrink-0"
            >
              <Download aria-hidden="true" />
              {zipCount > 1
                ? `Descargar ${zipCount} ZIP (uno por día) · ${selected.size} PDF`
                : `Descargar ZIP · ${selected.size} PDF`}
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
