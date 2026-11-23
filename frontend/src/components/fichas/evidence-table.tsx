"use client";

import { Fragment, useMemo, useState } from "react";
import { ArrowUpDown, ChevronRight } from "lucide-react";
import { EvidenceFilters } from "@/components/pending-grading/evidence-filters";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  EMPTY_FILTERS,
  applyFilters,
  compareGuides,
  guideOf,
  type PendingFilters,
} from "@/lib/pending-grading";
import { cn } from "@/lib/utils";
import type { EvidenceItem, StudentItem } from "@/types/api";

interface EvidenceTableProps {
  evidences: EvidenceItem[];
  /** Aprendices de la ficha: el detalle lista los activos sin nota. */
  students: StudentItem[];
  /** item_id → fecha de cierre del cronograma (vacío si no hay). */
  cutoffs: Map<number, string>;
}

type SortKey = "name" | "total_approved" | "total_disapproved" | "total_pending";

const NO_TYPES = new Map<number, string>();

function formatCutoff(date: string | undefined): string {
  if (!date) return "—";
  const [y, m, d] = date.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

function SortableHeader({
  label,
  field,
  onSort,
  className,
}: {
  label: string;
  field: SortKey;
  onSort: (field: SortKey) => void;
  className?: string;
}) {
  const numeric = className?.includes("text-right");
  return (
    <TableHead className={cn("select-none", className)}>
      <button
        type="button"
        onClick={() => onSort(field)}
        className={cn(
          "flex w-full items-center gap-1 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          numeric && "justify-end",
        )}
      >
        {label}
        <ArrowUpDown aria-hidden="true" className="h-3 w-3 text-muted-foreground" />
      </button>
    </TableHead>
  );
}

/**
 * Evidencias de la ficha con los filtros de Por Calificar. Con cronograma
 * abre en "Ya cerró": lo que aún no vence no es un pendiente real.
 */
export function EvidenceTable({ evidences, students, cutoffs }: EvidenceTableProps) {
  const [filters, setFilters] = useState<PendingFilters>(() =>
    cutoffs.size > 0 ? { ...EMPTY_FILTERS, closing: new Set(["vencida"]) } : EMPTY_FILTERS,
  );
  const [sortKey, setSortKey] = useState<SortKey>("total_pending");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const guides = useMemo(
    () =>
      [...new Set(evidences.map((e) => guideOf(e.name)).filter((g): g is string => g !== null))].sort(
        compareGuides,
      ),
    [evidences],
  );
  const phases = useMemo(() => [...new Set(evidences.map((e) => e.category))], [evidences]);
  const active = useMemo(() => students.filter((s) => s.status === "Activo"), [students]);

  const rows = useMemo(() => {
    const visible = applyFilters(evidences, filters, NO_TYPES, cutoffs);
    return [...visible].sort((a, b) => {
      const cmp =
        sortKey === "name" ? a.name.localeCompare(b.name) : (a[sortKey] as number) - (b[sortKey] as number);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [evidences, filters, cutoffs, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else {
      setSortKey(key);
      setSortDir(key === "name" ? "asc" : "desc");
    }
  };

  const toggleExpanded = (itemId: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });

  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-card">
      <div className="space-y-3 border-b px-4 py-3">
        <EvidenceFilters
          filters={filters}
          onChange={setFilters}
          onClear={() => setFilters(EMPTY_FILTERS)}
          guides={guides}
          phases={phases}
          hasCronograma={cutoffs.size > 0}
          showKind={false}
        />
        <p className="text-xs text-muted-foreground">
          <span className="font-semibold tabular-nums text-foreground">{rows.length}</span> de{" "}
          {evidences.length} evidencias · “Sin nota” cuenta aprendices activos, incluidos los que no han
          enviado.
        </p>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <SortableHeader label="Evidencia" field="name" onSort={toggleSort} className="pl-4" />
            <TableHead className="hidden w-24 md:table-cell">Cierre</TableHead>
            <SortableHeader label="Aprobadas" field="total_approved" onSort={toggleSort} className="w-24 text-right" />
            <SortableHeader
              label="Desaprobadas"
              field="total_disapproved"
              onSort={toggleSort}
              className="hidden w-28 text-right sm:table-cell"
            />
            <SortableHeader label="Sin nota" field="total_pending" onSort={toggleSort} className="w-24 text-right" />
            <TableHead className="hidden w-32 lg:table-cell">Avance</TableHead>
            <TableHead className="w-10 pr-4">
              <span className="sr-only">Detalle</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((ev) => {
            const total = ev.total_approved + ev.total_disapproved + ev.total_pending;
            const approvedPct = total > 0 ? (ev.total_approved / total) * 100 : 0;
            const disapprovedPct = total > 0 ? (ev.total_disapproved / total) * 100 : 0;
            const isOpen = expanded.has(ev.item_id);
            const missing = isOpen
              ? active.filter((s) => (s.grades[String(ev.item_id)]?.value ?? "-") === "-")
              : [];
            return (
              <Fragment key={ev.item_id}>
                <TableRow>
                  <TableCell className="max-w-0 whitespace-normal pl-4">
                    <p className="text-sm font-medium leading-snug text-foreground">{ev.name}</p>
                    <p className="text-xs text-muted-foreground">{ev.category}</p>
                  </TableCell>
                  <TableCell className="hidden text-xs tabular-nums text-muted-foreground md:table-cell">
                    {formatCutoff(cutoffs.get(ev.item_id))}
                  </TableCell>
                  <TableCell className="text-right font-semibold tabular-nums text-ok-fg">
                    {ev.total_approved}
                  </TableCell>
                  <TableCell
                    className={cn(
                      "hidden text-right font-semibold tabular-nums sm:table-cell",
                      ev.total_disapproved > 0 ? "text-danger-fg" : "text-muted-foreground",
                    )}
                  >
                    {ev.total_disapproved}
                  </TableCell>
                  <TableCell className="text-right font-semibold tabular-nums text-foreground">
                    {ev.total_pending}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div className="bg-ok" style={{ width: `${approvedPct}%` }} />
                      <div className="bg-danger" style={{ width: `${disapprovedPct}%` }} />
                    </div>
                  </TableCell>
                  <TableCell className="pr-4">
                    {ev.total_pending > 0 && (
                      <button
                        type="button"
                        aria-expanded={isOpen}
                        aria-label={isOpen ? "Ocultar aprendices sin nota" : "Ver aprendices sin nota"}
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
                {isOpen && (
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableCell colSpan={7} className="whitespace-normal px-4 py-3">
                      <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                        {missing.length} aprendices activos sin nota
                      </p>
                      <ul className="grid gap-x-6 gap-y-0.5 text-xs text-foreground sm:grid-cols-2 lg:grid-cols-3">
                        {missing.map((s) => (
                          <li key={s.user_id} className="truncate">
                            {s.full_name}
                          </li>
                        ))}
                      </ul>
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            );
          })}
          {rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                Ninguna evidencia coincide con los filtros
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </section>
  );
}
