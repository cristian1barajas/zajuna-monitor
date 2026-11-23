"use client";

import { useMemo, useState } from "react";
import { EvidenceFilters } from "@/components/pending-grading/evidence-filters";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import {
  EMPTY_FILTERS,
  applyFilters,
  compareGuides,
  guideOf,
  hasActiveFilters,
  type PendingFilters,
} from "@/lib/pending-grading";
import type { EvidenceItem } from "@/types/api";

interface EvidencePickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  evidences: EvidenceItem[];
  selected: Set<number>;
  onChange: (next: Set<number>) => void;
  /** item_id → fecha de cierre (YYYY-MM-DD) del cronograma. */
  cutoffs: Map<number, string>;
  /** item_id → assign/forum/quiz; vacío oculta el filtro de tipo. */
  moduleTypes?: Map<number, string>;
  title?: string;
}

const NO_TYPES = new Map<number, string>();

function formatCutoff(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

/**
 * Selector de evidencias en un panel: los mismos filtros de Por Calificar
 * (guía, fase, cierre) sobre la lista agrupada por fase. Lo comparten las
 * páginas que trabajan sobre un conjunto de evidencias.
 */
export function EvidencePicker({
  open,
  onOpenChange,
  evidences,
  selected,
  onChange,
  cutoffs,
  moduleTypes = NO_TYPES,
  title = "Elegir evidencias",
}: EvidencePickerProps) {
  const [filters, setFilters] = useState<PendingFilters>(EMPTY_FILTERS);

  const guides = useMemo(
    () =>
      [...new Set(evidences.map((e) => guideOf(e.name)).filter((g): g is string => g !== null))].sort(
        compareGuides,
      ),
    [evidences],
  );
  const phases = useMemo(() => [...new Set(evidences.map((e) => e.category))], [evidences]);
  const visible = useMemo(
    () => applyFilters(evidences, filters, moduleTypes, cutoffs),
    [evidences, filters, moduleTypes, cutoffs],
  );
  const grouped = useMemo(() => {
    const map = new Map<string, EvidenceItem[]>();
    for (const ev of visible) {
      const cat = ev.category || "Sin categoría";
      map.set(cat, [...(map.get(cat) ?? []), ev]);
    }
    return map;
  }, [visible]);

  const setMany = (ids: number[], select: boolean) => {
    const next = new Set(selected);
    for (const id of ids) {
      if (select) next.add(id);
      else next.delete(id);
    }
    onChange(next);
  };

  /** Marca desde la primera evidencia del curso hasta esta, en orden. */
  const selectUpTo = (itemId: number) => {
    const next = new Set<number>();
    for (const ev of evidences) {
      next.add(ev.item_id);
      if (ev.item_id === itemId) break;
    }
    onChange(next);
  };

  const visibleIds = visible.map((e) => e.item_id);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={title}
        subtitle="Filtra y marca las evidencias. Con el cronograma cargado, “Cierre: Ya cerró” deja solo las vencidas."
        className="max-w-4xl"
        footer={
          <>
            <span className="text-sm text-muted-foreground">
              <span className="font-semibold tabular-nums text-foreground">{selected.size}</span> de{" "}
              <span className="tabular-nums">{evidences.length}</span> seleccionadas
            </span>
            <Button onClick={() => onOpenChange(false)}>Listo</Button>
          </>
        }
      >
        {/* Filtros fijos arriba mientras la lista hace scroll */}
        <div className="sticky top-0 z-10 space-y-3 border-b bg-card px-6 py-4">
          <EvidenceFilters
            filters={filters}
            onChange={setFilters}
            onClear={() => setFilters(EMPTY_FILTERS)}
            guides={guides}
            phases={phases}
            hasCronograma={cutoffs.size > 0}
            showKind={moduleTypes.size > 0}
          />
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Button variant="outline" size="sm" pill onClick={() => setMany(visibleIds, true)}>
              Marcar {hasActiveFilters(filters) ? `las ${visibleIds.length} visibles` : "todas"}
            </Button>
            <Button variant="outline" size="sm" pill onClick={() => setMany(visibleIds, false)}>
              Quitar {hasActiveFilters(filters) ? "las visibles" : "todas"}
            </Button>
          </div>
        </div>

        <div className="divide-y">
          {[...grouped.entries()].map(([cat, items]) => {
            const ids = items.map((e) => e.item_id);
            const chosen = ids.filter((id) => selected.has(id)).length;
            const all = chosen === ids.length;
            return (
              <section key={cat}>
                <label className="flex cursor-pointer items-center gap-3 bg-muted/40 px-6 py-2 text-sm font-semibold text-foreground">
                  <input
                    type="checkbox"
                    checked={all}
                    ref={(el) => {
                      if (el) el.indeterminate = chosen > 0 && !all;
                    }}
                    onChange={() => setMany(ids, !all)}
                    className="rounded"
                  />
                  <span className="min-w-0 flex-1 truncate">{cat}</span>
                  <span className="text-xs font-normal tabular-nums text-muted-foreground">
                    {chosen}/{ids.length}
                  </span>
                </label>
                <ul>
                  {items.map((ev) => {
                    const cutoff = cutoffs.get(ev.item_id);
                    return (
                      <li
                        key={ev.item_id}
                        className="group flex items-start gap-3 px-6 py-1.5 transition-colors duration-150 ease-out hover:bg-muted/50"
                      >
                        <input
                          id={`ev-${ev.item_id}`}
                          type="checkbox"
                          checked={selected.has(ev.item_id)}
                          onChange={() => setMany([ev.item_id], !selected.has(ev.item_id))}
                          className="mt-0.5 rounded"
                        />
                        <label
                          htmlFor={`ev-${ev.item_id}`}
                          className="min-w-0 flex-1 cursor-pointer text-sm leading-snug text-foreground"
                        >
                          {ev.name}
                        </label>
                        {cutoff && (
                          <span className="shrink-0 pt-0.5 text-xs tabular-nums text-muted-foreground">
                            {formatCutoff(cutoff)}
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => selectUpTo(ev.item_id)}
                          title="Marca todas las evidencias del curso hasta esta, en orden"
                          className="shrink-0 rounded px-1.5 pt-0.5 text-xs font-medium text-sena-green-dark opacity-0 transition-opacity duration-150 hover:underline focus-visible:opacity-100 group-hover:opacity-100 dark:text-sena-green"
                        >
                          Hasta aquí
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
          {visible.length === 0 && (
            <p className="px-6 py-10 text-center text-sm text-muted-foreground">
              Ninguna evidencia coincide con los filtros
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
