"use client";

import { Fragment, useState } from "react";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ArrowRight, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { StageBadge } from "./stage-badge";
import type { DueProcessRecord } from "@/types/api";

interface DueProcessTableProps {
  records: DueProcessRecord[];
  ficha: string;
  /** Hay una etapa elegida: el vacío no significa que no haya registros. */
  filtered?: boolean;
}

const COLUMNS = 7;

const LINK_CLASS =
  "inline-flex items-center gap-1 rounded-sm text-xs font-semibold text-sena-green-dark transition-colors duration-150 ease-out hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-sena-green";

function dayOf(date: string): string {
  return date.includes("T") ? date.split("T")[0] : date;
}

export function DueProcessTable({ records, ficha, filtered = false }: DueProcessTableProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const reportsHref = `/fichas/${ficha}/reportes`;

  const toggleExpand = (userId: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  if (records.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed bg-card px-6 py-12 text-center shadow-card">
        <p className="text-sm font-medium text-foreground">
          {filtered ? "Ningún aprendiz en esta etapa" : "Sin registros de debido proceso"}
        </p>
        {!filtered && (
          <p className="mt-1 text-sm text-muted-foreground">
            Genera los correos desde{" "}
            <Link href={reportsHref} className={LINK_CLASS}>
              Reportes
            </Link>{" "}
            para iniciar el proceso.
          </p>
        )}
      </div>
    );
  }

  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <span className="sr-only">Historial</span>
            </TableHead>
            <TableHead>Aprendiz</TableHead>
            <TableHead className="hidden w-28 sm:table-cell">Cédula</TableHead>
            <TableHead className="w-36">Etapa actual</TableHead>
            <TableHead className="w-28">Último llamado</TableHead>
            <TableHead className="w-20 text-center">Etapas</TableHead>
            <TableHead className="w-36">
              <span className="sr-only">Acción</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {records.map((record) => {
            const isExpanded = expanded.has(record.user_id);
            const lastHistory =
              record.history.length > 0
                ? record.history[record.history.length - 1]
                : null;

            return (
              <Fragment key={record.user_id}>
                <TableRow>
                  <TableCell>
                    <button
                      type="button"
                      onClick={() => toggleExpand(record.user_id)}
                      aria-expanded={isExpanded}
                      aria-label={
                        isExpanded
                          ? `Ocultar historial de ${record.full_name}`
                          : `Ver historial de ${record.full_name}`
                      }
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 ease-out hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <ChevronRight
                        aria-hidden="true"
                        className={cn("h-4 w-4 transition-transform duration-150", isExpanded && "rotate-90")}
                      />
                    </button>
                  </TableCell>
                  <TableCell className="font-medium">{record.full_name}</TableCell>
                  <TableCell className="hidden font-mono text-sm tabular-nums sm:table-cell">
                    {record.document}
                  </TableCell>
                  <TableCell>
                    <StageBadge stage={record.current_stage} />
                  </TableCell>
                  <TableCell className="text-sm tabular-nums text-muted-foreground">
                    {lastHistory ? dayOf(lastHistory.date) : "-"}
                  </TableCell>
                  <TableCell className="text-center text-sm font-semibold tabular-nums text-foreground">
                    {record.history.length}
                  </TableCell>
                  <TableCell className="pr-4">
                    {record.current_stage !== "comite" && (
                      <Link
                        href={reportsHref}
                        aria-label={`Siguiente llamado de ${record.full_name}`}
                        className={LINK_CLASS}
                      >
                        Siguiente llamado
                        <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
                      </Link>
                    )}
                  </TableCell>
                </TableRow>
                {isExpanded && (
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableCell />
                    <TableCell colSpan={COLUMNS - 1} className="py-3 whitespace-normal">
                      <p className="mb-2 text-xs font-medium text-muted-foreground">
                        Historial del debido proceso
                      </p>
                      <ol className="divide-y rounded-md border bg-card">
                        {record.history.map((entry, i) => (
                          <li key={i} className="flex items-start gap-3 px-3 py-2 text-xs">
                            <div className="flex-shrink-0 pt-0.5">
                              <StageBadge stage={entry.stage} />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-medium text-foreground">{entry.stage_label}</p>
                              <p className="tabular-nums text-muted-foreground">{dayOf(entry.date)}</p>
                              {entry.evidence_names.length > 0 && (
                                <p className="mt-1 text-muted-foreground">
                                  Evidencias: {entry.evidence_names.join(", ")}
                                </p>
                              )}
                            </div>
                          </li>
                        ))}
                      </ol>
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            );
          })}
        </TableBody>
      </Table>
    </section>
  );
}
