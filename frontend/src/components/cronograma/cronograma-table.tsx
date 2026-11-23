"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CronogramaEntry } from "@/types/api";

interface CronogramaTableProps {
  entries: CronogramaEntry[];
  onRemoveEntry?: (index: number) => void;
  editable?: boolean;
  /** Hay cambios sin guardar: el vínculo con Zajuna aún no se ha verificado. */
  unsaved?: boolean;
  /** Filas que trae la última carga de PDF, por nombre de evidencia. */
  changes?: Map<string, CronogramaChange>;
}

export type CronogramaChange = { kind: "new" } | { kind: "date"; previous: string };

/**
 * Filas del cronograma pensadas para vivir dentro de una sección con
 * cabecera propia (ver página de cronograma): la tabla va al ras, con
 * reglas de 1px entre filas y la acción de borrar revelada en hover.
 * Se ordena por fecha de corte; onRemoveEntry recibe el índice original.
 */
export function CronogramaTable({
  entries,
  onRemoveEntry,
  editable = false,
  unsaved = false,
  changes,
}: CronogramaTableProps) {
  if (entries.length === 0) {
    return (
      <p className="px-4 py-8 text-center text-sm text-muted-foreground">
        No hay entradas en el cronograma.
      </p>
    );
  }

  const rows = entries
    .map((entry, index) => ({ entry, index }))
    .sort((a, b) => a.entry.cutoff_date.localeCompare(b.entry.cutoff_date));

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10 pl-4">#</TableHead>
          <TableHead>Evidencia</TableHead>
          <TableHead className="w-36">Fecha de corte</TableHead>
          <TableHead className={cn("w-28", !editable && "pr-4")}>
            Vinculada
          </TableHead>
          {editable && <TableHead className="w-16 pr-4" />}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(({ entry, index }, position) => {
          const change = changes?.get(entry.evidence_name);
          return (
          <TableRow
            key={`${entry.evidence_name}-${index}`}
            className={cn("group transition-colors duration-150 ease-out", change && "bg-warn-soft/40")}
          >
            <TableCell className="pl-4 tabular-nums text-muted-foreground">
              {position + 1}
            </TableCell>
            <TableCell className="font-medium">
              {entry.evidence_name}
              {change && (
                <span className="ml-2 inline-flex items-center rounded-full border border-warn-border bg-warn-soft px-2 py-0.5 text-[11px] font-medium text-warn-fg">
                  {change.kind === "new" ? "Nueva" : "Cambia fecha"}
                </span>
              )}
            </TableCell>
            <TableCell className="tabular-nums">
              {entry.cutoff_date}
              {change?.kind === "date" && (
                <span className="block text-xs text-muted-foreground line-through">{change.previous}</span>
              )}
            </TableCell>
            <TableCell className={cn(!editable && "pr-4")}>
              {entry.evidence_item_id ? (
                <span className="inline-flex items-center rounded-full border border-ok-border bg-ok-soft px-2 py-0.5 text-[11px] font-medium tabular-nums text-ok-fg">
                  ID {entry.evidence_item_id}
                </span>
              ) : (
                <span className="inline-flex items-center rounded-full border border-pending-border bg-pending-soft px-2 py-0.5 text-[11px] font-medium text-pending-fg">
                  {unsaved ? "Sin verificar" : "No encontrada"}
                </span>
              )}
            </TableCell>
            {editable && onRemoveEntry && (
              <TableCell className="pr-4">
                <button
                  type="button"
                  onClick={() => onRemoveEntry(index)}
                  aria-label={`Quitar ${entry.evidence_name} del cronograma`}
                  className="cursor-pointer rounded-md p-1 text-muted-foreground opacity-0 transition-[color,background-color,opacity] duration-150 ease-out hover:bg-danger-soft hover:text-danger-fg focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-hover:opacity-100"
                >
                  <Trash2 aria-hidden="true" className="h-4 w-4" />
                </button>
              </TableCell>
            )}
          </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
