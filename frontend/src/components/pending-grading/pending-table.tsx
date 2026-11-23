"use client";

import { Fragment, useState } from "react";
import Link from "next/link";
import { ChevronRight, Download, Loader2, RotateCw } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { kindOf, type EvidenceKind } from "@/lib/pending-grading";
import { cn } from "@/lib/utils";
import type { EvidenceItem, PendingGradingResult } from "@/types/api";

export type RowState = "queued" | "checking";

interface PendingTableProps {
  rows: EvidenceItem[];
  selected: Set<number>;
  onToggle: (itemId: number) => void;
  onToggleAll: (itemIds: number[], select: boolean) => void;
  results: Map<number, PendingGradingResult>;
  rowStates: Map<number, RowState>;
  moduleTypes: Map<number, string>;
  cutoffs: Map<number, string>;
  disabled: boolean;
  emptyMessage: string;
  /** Con la ficha, el detalle de una tarea enlaza a descargar solo esa tarea */
  ficha?: string;
  /** Vuelve a consultar una evidencia que falló */
  onRetry?: (itemId: number) => void;
}

const KIND_BADGE: Partial<Record<EvidenceKind, { label: string; className: string }>> = {
  forum: { label: "Foro", className: "bg-notice-soft text-notice-fg" },
  quiz: { label: "Cuestionario", className: "bg-info-soft text-info-fg" },
};

function formatCutoff(date: string | undefined): string {
  if (!date) return "—";
  const [y, m, d] = date.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

function Dash() {
  return <span className="text-muted-foreground/60">—</span>;
}

function RetryButton({ onRetry, disabled, label }: { onRetry: () => void; disabled: boolean; label?: string }) {
  return (
    <button
      type="button"
      onClick={onRetry}
      disabled={disabled}
      aria-label={label ? undefined : "Reintentar"}
      title="Volver a consultar en Zajuna"
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs font-medium text-sena-green-dark hover:bg-muted disabled:pointer-events-none disabled:opacity-50 dark:text-sena-green"
    >
      <RotateCw aria-hidden="true" className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

function PendingCell({
  result,
  state,
  onRetry,
  disabled,
}: {
  result?: PendingGradingResult;
  state?: RowState;
  onRetry?: () => void;
  disabled: boolean;
}) {
  if (state === "checking") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
        Consultando
      </span>
    );
  }
  if (state === "queued") return <span className="text-xs text-muted-foreground">En cola</span>;
  if (!result) return <Dash />;
  if (result.error) {
    return (
      <span className="inline-flex items-center gap-0.5">
        <span className="text-xs font-medium text-warn-fg" title={result.error}>
          No se pudo consultar
        </span>
        {onRetry && <RetryButton onRetry={onRetry} disabled={disabled} />}
      </span>
    );
  }
  if (result.module_type === "quiz") {
    return <span className="text-xs text-info-fg">Automático</span>;
  }
  const count = result.needs_grading ?? 0;
  return count > 0 ? (
    <span className="inline-flex min-w-7 justify-center rounded-full border border-danger-border bg-danger-soft px-2 py-0.5 text-xs font-bold tabular-nums text-danger-fg">
      {count}
    </span>
  ) : (
    <span className="text-xs font-medium text-ok-fg">Al día</span>
  );
}

function submittedOf(result: PendingGradingResult): number | null {
  if (result.module_type === "quiz") {
    return (result.quiz_approved ?? 0) + (result.quiz_disapproved ?? 0);
  }
  return result.submitted;
}

function hasDetail(result?: PendingGradingResult): boolean {
  if (!result) return false;
  if (result.error) return true;
  if (result.module_type === "assign") return result.pending_students.length > 0;
  return true;
}

function DetailRow({
  result,
  ficha,
  onRetry,
  disabled,
}: {
  result: PendingGradingResult;
  ficha?: string;
  onRetry?: () => void;
  disabled: boolean;
}) {
  if (result.error) {
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p className="text-xs text-warn-fg">{result.error}</p>
        {onRetry && <RetryButton onRetry={onRetry} disabled={disabled} label="Reintentar" />}
      </div>
    );
  }
  if (result.module_type === "quiz") {
    return (
      <p className="text-xs text-muted-foreground">
        {result.quiz_approved ?? 0} aprobados · {result.quiz_disapproved ?? 0} desaprobados ·{" "}
        {result.quiz_pending ?? 0} sin presentar. Zajuna los califica solo.
      </p>
    );
  }
  if (result.module_type === "forum") {
    return (
      <p className="text-xs text-muted-foreground">
        {result.needs_grading ?? 0} participaciones sin calificar en{" "}
        {result.total_discussions ?? 0} discusiones. Los foros se califican dentro de Zajuna.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <ul className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        {result.pending_students.map((s) => (
          <li key={s.user_id} className="flex min-w-0 items-baseline justify-between gap-3 text-xs">
            <span className="truncate font-medium text-foreground">{s.full_name}</span>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {s.last_modified ?? "Sin fecha"}
              {s.file_count > 1 && ` · ${s.file_count} archivos`}
            </span>
          </li>
        ))}
      </ul>
      {ficha && result.cmid != null && (
        <Link
          href={`/fichas/${ficha}/descargar-evidencias?cmid=${result.cmid}`}
          className="inline-flex items-center gap-1 text-xs font-medium text-sena-green-dark underline-offset-2 hover:underline dark:text-sena-green"
        >
          <Download aria-hidden="true" className="h-3.5 w-3.5" />
          Descargar solo esta tarea
        </Link>
      )}
    </div>
  );
}

export function PendingTable({
  rows,
  selected,
  onToggle,
  onToggleAll,
  results,
  rowStates,
  moduleTypes,
  cutoffs,
  disabled,
  emptyMessage,
  ficha,
  onRetry,
}: PendingTableProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const rowIds = rows.map((r) => r.item_id);
  const allSelected = rows.length > 0 && rowIds.every((id) => selected.has(id));

  const toggleExpanded = (itemId: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10">
            <input
              type="checkbox"
              aria-label={allSelected ? "Quitar todas las visibles" : "Seleccionar todas las visibles"}
              checked={allSelected}
              disabled={disabled || rows.length === 0}
              onChange={() => onToggleAll(rowIds, !allSelected)}
              className="rounded"
            />
          </TableHead>
          <TableHead>Evidencia</TableHead>
          <TableHead className="hidden w-24 md:table-cell">Cierre</TableHead>
          <TableHead className="w-20 text-center">Enviados</TableHead>
          <TableHead className="hidden w-24 text-center sm:table-cell">Borradores</TableHead>
          <TableHead className="w-28 text-center">Por calificar</TableHead>
          <TableHead className="w-10">
            <span className="sr-only">Detalle</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((ev) => {
          const result = results.get(ev.item_id);
          const kind = kindOf(ev.item_id, moduleTypes);
          const badge = KIND_BADGE[kind];
          const isOpen = expanded.has(ev.item_id);
          const detail = hasDetail(result);
          return (
            <Fragment key={ev.item_id}>
              <TableRow data-state={selected.has(ev.item_id) ? "selected" : undefined}>
                <TableCell>
                  <input
                    type="checkbox"
                    aria-label={`Seleccionar ${ev.name}`}
                    checked={selected.has(ev.item_id)}
                    disabled={disabled}
                    onChange={() => onToggle(ev.item_id)}
                    className="rounded"
                  />
                </TableCell>
                <TableCell className="max-w-0">
                  <div className="flex min-w-0 items-center gap-1.5">
                    <span className="truncate text-sm font-medium" title={ev.name}>
                      {ev.name}
                    </span>
                    {badge && (
                      <span
                        className={cn(
                          "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium",
                          badge.className,
                        )}
                      >
                        {badge.label}
                      </span>
                    )}
                  </div>
                  <p className="truncate text-xs text-muted-foreground">{ev.category}</p>
                </TableCell>
                <TableCell className="hidden text-xs tabular-nums text-muted-foreground md:table-cell">
                  {formatCutoff(cutoffs.get(ev.item_id))}
                </TableCell>
                <TableCell className="text-center text-sm tabular-nums">
                  {result && !result.error ? submittedOf(result) ?? <Dash /> : <Dash />}
                </TableCell>
                <TableCell className="hidden text-center text-sm tabular-nums sm:table-cell">
                  {result && !result.error && kind === "assign" ? result.drafts ?? <Dash /> : <Dash />}
                </TableCell>
                <TableCell className="text-center">
                  <PendingCell
                    result={result}
                    state={rowStates.get(ev.item_id)}
                    onRetry={onRetry && (() => onRetry(ev.item_id))}
                    disabled={disabled}
                  />
                </TableCell>
                <TableCell>
                  {detail && (
                    <button
                      type="button"
                      aria-expanded={isOpen}
                      aria-label={isOpen ? "Ocultar detalle" : "Ver detalle"}
                      onClick={() => toggleExpanded(ev.item_id)}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <ChevronRight
                        aria-hidden="true"
                        className={cn("h-4 w-4 transition-transform duration-150", isOpen && "rotate-90")}
                      />
                    </button>
                  )}
                </TableCell>
              </TableRow>
              {isOpen && result && (
                <TableRow className="bg-muted/40 hover:bg-muted/40">
                  <TableCell />
                  <TableCell colSpan={6} className="py-3 whitespace-normal">
                    <DetailRow
                      result={result}
                      ficha={ficha}
                      onRetry={onRetry && (() => onRetry(ev.item_id))}
                      disabled={disabled}
                    />
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          );
        })}
        {rows.length === 0 && (
          <TableRow>
            <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
              {emptyMessage}
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
