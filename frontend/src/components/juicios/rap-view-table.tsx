"use client";

import { Fragment, useMemo, useState } from "react";
import { RapStatusBadge } from "./rap-status-badge";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StudentCrossResult, RapCrossResult } from "@/types/api";

interface RapViewTableProps {
  students: StudentCrossResult[];
}

interface RapGroup {
  rap: string;
  competencia: string;
  results: { document: string; full_name: string; result: RapCrossResult }[];
  counts: Record<string, number>;
}

/**
 * Tabla por RAP: superficie única con cabecera integrada (contador) y
 * filas divididas por reglas de 1px. Cada fila expande los aprendices
 * evaluados en ese RAP.
 */
export function RapViewTable({ students }: RapViewTableProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (rap: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(rap)) next.delete(rap);
      else next.add(rap);
      return next;
    });
  };

  // Group by RAP across all students
  const raps = useMemo(() => {
    const rapMap = new Map<string, RapGroup>();

    for (const student of students) {
      for (const rap of student.raps) {
        if (!rapMap.has(rap.rap)) {
          rapMap.set(rap.rap, {
            rap: rap.rap,
            competencia: rap.competencia,
            results: [],
            counts: {},
          });
        }
        const group = rapMap.get(rap.rap)!;
        group.results.push({
          document: student.document,
          full_name: student.full_name,
          result: rap,
        });
        group.counts[rap.resultado] = (group.counts[rap.resultado] ?? 0) + 1;
      }
    }

    return Array.from(rapMap.values());
  }, [students]);

  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-card">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">
          Resultados de aprendizaje{" "}
          <span className="font-normal tabular-nums text-muted-foreground">
            {raps.length}
          </span>
        </h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground">
              <th className="w-8 p-3"></th>
              <th className="p-3 text-left font-medium">RAP</th>
              <th className="p-3 text-left font-medium">Competencia</th>
              <th className="p-3 text-center font-medium">Est.</th>
              <th className="p-3 text-center font-medium">Listos</th>
              <th className="p-3 text-center font-medium">OK</th>
              <th className="p-3 text-center font-medium">Pend.</th>
              <th className="p-3 text-center font-medium">Probl.</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {raps.map((group) => (
              <Fragment key={group.rap}>
                <tr
                  onClick={() => toggle(group.rap)}
                  className="group cursor-pointer transition-colors duration-150 ease-out hover:bg-muted/60"
                >
                  <td className="p-3">
                    <ChevronRight
                      aria-hidden="true"
                      className={cn(
                        "h-4 w-4 text-muted-foreground transition-transform duration-150 ease-out",
                        expanded.has(group.rap) && "rotate-90"
                      )}
                    />
                  </td>
                  <td className="p-3 font-medium text-foreground">
                    {group.rap.split(" - ").slice(-1)[0]}
                  </td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {group.competencia.split(" - ").slice(-1)[0]}
                  </td>
                  <td className="p-3 text-center tabular-nums text-foreground">
                    {group.results.length}
                  </td>
                  <td className="p-3 text-center font-semibold tabular-nums text-info-fg">
                    {group.counts.listo_para_aprobar || ""}
                  </td>
                  <td className="p-3 text-center tabular-nums text-ok-fg">
                    {group.counts.correcto || ""}
                  </td>
                  <td className="p-3 text-center tabular-nums text-pending-fg">
                    {group.counts.pendiente || ""}
                  </td>
                  <td className="p-3 text-center tabular-nums text-danger-fg">
                    {(group.counts.con_problemas ?? 0) +
                      (group.counts.inconsistencia ?? 0) || ""}
                  </td>
                </tr>
                {expanded.has(group.rap) && (
                  <tr>
                    <td colSpan={8} className="bg-muted/40 p-0">
                      <div className="max-h-64 overflow-auto px-6 py-3">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-muted-foreground">
                              <th className="pb-2 text-left font-medium">
                                Aprendiz
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
                            {group.results.map((r, i) => (
                              <tr key={i} className="border-t">
                                <td className="py-1.5 text-foreground">
                                  {r.full_name}
                                </td>
                                <td className="py-1.5 text-center tabular-nums">
                                  {r.result.evidencias_aprobadas}/
                                  {r.result.evidencias_total}
                                </td>
                                <td className="py-1.5 text-center">
                                  {r.result.sofia_juicio}
                                </td>
                                <td className="py-1.5">
                                  <RapStatusBadge
                                    resultado={r.result.resultado}
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
