"use client";

import { Fragment, useState } from "react";
import { RapStatusBadge, resultadoLabel } from "./rap-status-badge";
import { hasStatus, needsAction, type RapStatus } from "./student-filters";
import { ChevronRight, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StudentCrossResult } from "@/types/api";

type View = "accion" | "todos";

interface StudentRapTableProps {
  students: StudentCrossResult[];
  /** Filtro por estado desde la franja de KPIs; tiene prioridad sobre la vista */
  statusFilter?: RapStatus | null;
  onClearStatus?: () => void;
}

/**
 * Tabla por aprendiz: superficie única con cabecera integrada
 * (vista + contador) y filas divididas por reglas de 1px. Cada fila
 * expande el detalle de RAPs del aprendiz.
 */
export function StudentRapTable({ students, statusFilter = null, onClearStatus }: StudentRapTableProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  // Por defecto se ve lo que requiere acción; si no hay nada, todos
  const [view, setView] = useState<View>(() => (students.some(needsAction) ? "accion" : "todos"));

  const toggle = (doc: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(doc)) next.delete(doc);
      else next.add(doc);
      return next;
    });
  };

  const actionable = students.filter(needsAction);
  const filtered = statusFilter
    ? students.filter((s) => hasStatus(s, statusFilter))
    : view === "accion"
      ? actionable
      : students;

  const selectView = (value: View) => {
    setView(value);
    onClearStatus?.();
  };

  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <div role="radiogroup" aria-label="Qué aprendices mostrar" className="inline-flex rounded-full border p-0.5">
            {(
              [
                ["accion", `Requiere acción (${actionable.length})`],
                ["todos", `Todos (${students.length})`],
              ] as const
            ).map(([value, label]) => {
              const checked = !statusFilter && view === value;
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={checked}
                  onClick={() => selectView(value)}
                  className={cn(
                    "h-7 rounded-full px-3 text-xs font-medium transition-colors duration-150 ease-out",
                    checked ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                </button>
              );
            })}
          </div>
          {statusFilter && (
            <button
              type="button"
              onClick={onClearStatus}
              className="inline-flex h-7 items-center gap-1 rounded-full border border-primary px-3 text-xs font-medium text-foreground transition-colors duration-150 ease-out hover:bg-accent"
            >
              Con RAP {resultadoLabel(statusFilter).toLowerCase()}
              <X aria-hidden="true" className="h-3 w-3" />
              <span className="sr-only">Quitar filtro</span>
            </button>
          )}
        </div>
        <p className="text-xs tabular-nums text-muted-foreground">
          {filtered.length} de {students.length} aprendices
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground">
              <th className="w-8 p-3"></th>
              <th className="p-3 text-left font-medium">Aprendiz</th>
              <th className="p-3 text-left font-medium">Documento</th>
              <th className="p-3 text-center font-medium">Total</th>
              <th className="p-3 text-center font-medium">Listos</th>
              <th className="p-3 text-center font-medium">OK</th>
              <th className="p-3 text-center font-medium">Pend.</th>
              <th className="p-3 text-center font-medium">Probl.</th>
              <th className="p-3 text-center font-medium">Incons.</th>
              <th className="p-3 text-center font-medium">Antic.</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filtered.length === 0 && (
              <tr>
                <td colSpan={10} className="p-8 text-center text-sm text-muted-foreground">
                  {view === "accion" && !statusFilter
                    ? "Ningún aprendiz tiene RAPs listos para aprobar, con problemas o inconsistentes"
                    : "Ningún aprendiz coincide con el filtro"}
                </td>
              </tr>
            )}
            {filtered.map((student) => (
              <Fragment key={student.document}>
                <tr
                  onClick={() => toggle(student.document)}
                  className="group cursor-pointer transition-colors duration-150 ease-out hover:bg-muted/60"
                >
                  <td className="p-3">
                    <ChevronRight
                      aria-hidden="true"
                      className={cn(
                        "h-4 w-4 text-muted-foreground transition-transform duration-150 ease-out",
                        expanded.has(student.document) && "rotate-90"
                      )}
                    />
                  </td>
                  <td className="p-3 font-medium text-foreground">
                    {student.full_name}
                  </td>
                  <td className="p-3 font-mono text-xs text-muted-foreground">
                    {student.document}
                  </td>
                  <td className="p-3 text-center tabular-nums text-foreground">
                    {student.total_raps}
                  </td>
                  <td className="p-3 text-center font-semibold tabular-nums text-info-fg">
                    {student.listos_para_aprobar || ""}
                  </td>
                  <td className="p-3 text-center tabular-nums text-ok-fg">
                    {student.correctos || ""}
                  </td>
                  <td className="p-3 text-center tabular-nums text-pending-fg">
                    {student.pendientes || ""}
                  </td>
                  <td className="p-3 text-center tabular-nums text-warn-fg">
                    {student.con_problemas || ""}
                  </td>
                  <td className="p-3 text-center tabular-nums text-danger-fg">
                    {student.inconsistencias || ""}
                  </td>
                  <td className="p-3 text-center tabular-nums text-notice-fg">
                    {student.aprobados_anticipados || ""}
                  </td>
                </tr>
                {expanded.has(student.document) && (
                  <tr>
                    <td colSpan={10} className="bg-muted/40 p-0">
                      <div className="max-h-80 overflow-auto px-6 py-3">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-muted-foreground">
                              <th className="pb-2 text-left font-medium">
                                RAP
                              </th>
                              <th className="pb-2 text-left font-medium">
                                Competencia
                              </th>
                              <th className="pb-2 text-center font-medium">
                                Evidencias
                              </th>
                              <th className="pb-2 text-center font-medium">
                                Sofia
                              </th>
                              <th className="pb-2 text-left font-medium">
                                Estado
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {student.raps.map((rap, i) => (
                              <tr key={i} className="border-t">
                                <td className="py-1.5 pr-2 text-foreground">
                                  {rap.rap.split(" - ").slice(-1)[0]}
                                </td>
                                <td className="py-1.5 pr-2 text-muted-foreground">
                                  {rap.competencia.split(" - ").slice(-1)[0]}
                                </td>
                                <td className="py-1.5 text-center tabular-nums">
                                  {rap.evidencias_aprobadas}/
                                  {rap.evidencias_total}
                                </td>
                                <td className="py-1.5 text-center">
                                  {rap.sofia_juicio}
                                </td>
                                <td className="py-1.5">
                                  <RapStatusBadge
                                    resultado={rap.resultado}
                                    compact
                                  />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
