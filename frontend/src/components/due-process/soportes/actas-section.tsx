"use client";

import { CheckCircle2, CircleAlert, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { FechaActa } from "@/types/api";
import { dayParts, formatDay, stageInfo } from "./stages";

interface ActasSectionProps {
  fechas: FechaActa[];
  onGenerate: (fecha: FechaActa) => void;
}

/**
 * Un acta por día de envío: relación de los llamados de ese día (de Debido
 * proceso) con la hora real del correo cuando ya se descargó su soporte.
 */
export function ActasSection({ fechas, onGenerate }: ActasSectionProps) {
  return (
    <section
      aria-labelledby="actas-titulo"
      className="rounded-xl border bg-card shadow-card"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b px-4 py-3">
        <h2 id="actas-titulo" className="text-sm font-semibold">
          Actas del equipo ejecutor
        </h2>
        <span className="text-xs text-muted-foreground">
          Word con la relación de llamados de cada día y firmas en blanco
        </span>
      </div>
      {fechas.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">
          Aún no hay llamados registrados en este grupo.
        </p>
      ) : (
        <ul className="divide-y">
          {fechas.map((f) => {
            const p = dayParts(f.fecha_envio);
            const completos = f.soportes >= f.llamados;
            return (
              <li
                key={f.fecha_envio}
                className="grid items-center gap-3 px-4 py-3 sm:grid-cols-[auto_minmax(0,1fr)_auto_auto]"
              >
                <div className="flex items-center gap-3">
                  <span className="flex w-12 shrink-0 flex-col items-center rounded-lg border bg-muted/40 py-1 leading-none">
                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {p.weekday}
                    </span>
                    <span className="text-lg font-bold tabular-nums">
                      {p.day}
                    </span>
                  </span>
                  <span className="text-sm font-medium capitalize sm:hidden">
                    {p.month}
                  </span>
                </div>
                <div className="min-w-0">
                  <p className="hidden text-sm font-medium capitalize sm:block">
                    {p.month} · {f.llamados}{" "}
                    {f.llamados === 1 ? "llamado" : "llamados"}
                  </p>
                  <p className="mt-0.5 flex flex-wrap gap-x-2.5 gap-y-0.5">
                    {Object.entries(f.por_etapa).map(([stage, n]) => {
                      const s = stageInfo(stage);
                      return (
                        <span
                          key={stage}
                          className="inline-flex items-center gap-1 text-[11px] text-muted-foreground"
                        >
                          <span
                            aria-hidden="true"
                            className={cn(
                              "h-1.5 w-1.5 rounded-full",
                              s?.dot ?? "bg-muted-foreground"
                            )}
                          />
                          {s?.short ?? stage}{" "}
                          <span className="font-semibold tabular-nums text-foreground">
                            {n}
                          </span>
                        </span>
                      );
                    })}
                  </p>
                </div>
                <p
                  className={cn(
                    "flex items-center gap-1.5 text-xs",
                    completos ? "text-ok-fg" : "text-warn-fg"
                  )}
                  title={
                    completos
                      ? "Todos los correos de ese día tienen su PDF descargado"
                      : "Descarga los soportes de ese día para que el acta lleve la hora de envío de cada correo"
                  }
                >
                  {completos ? (
                    <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                  ) : (
                    <CircleAlert aria-hidden="true" className="h-4 w-4" />
                  )}
                  {f.soportes} de {f.llamados} soportes
                </p>
                <div className="flex items-center gap-2 sm:justify-end">
                  {f.acta_numero && (
                    <span className="text-xs text-muted-foreground">
                      Acta No. {f.acta_numero}
                    </span>
                  )}
                  <Button
                    variant={f.acta_numero ? "outline" : "outline-primary"}
                    size="sm"
                    onClick={() => onGenerate(f)}
                    aria-label={`Generar acta del ${formatDay(f.fecha_envio)}`}
                  >
                    <FileText aria-hidden="true" />
                    {f.acta_numero ? "Volver a generar" : "Generar acta"}
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
