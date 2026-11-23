"use client";

import { Search } from "lucide-react";
import {
  SUBSET_LABELS,
  type FilterMode,
  type StudentCounts,
  type StudentSubset,
} from "@/lib/overdue-students";
import { cn } from "@/lib/utils";

interface OverdueFilterBarProps {
  totalCount: number;
  counts: StudentCounts;
  filterMode: FilterMode;
  onFilterModeChange: (mode: FilterMode) => void;
  subset: StudentSubset;
  onSubsetChange: (subset: StudentSubset) => void;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
}

const SUBSETS = Object.keys(SUBSET_LABELS) as StudentSubset[];

/**
 * Búsqueda + estado (segmentado) + subconjunto (menú) de la tabla de
 * aprendices. Reemplaza las siete pestañas que competían en una sola fila.
 */
export function OverdueFilterBar({
  totalCount,
  counts,
  filterMode,
  onFilterModeChange,
  subset,
  onSubsetChange,
  searchQuery,
  onSearchQueryChange,
}: OverdueFilterBarProps) {
  const modes: [FilterMode, string][] = [
    ["overdue", `Pendientes (${counts.overdueCount})`],
    ["al_dia", `Al día (${counts.alDiaCount})`],
    ["all", `Todos (${totalCount})`],
  ];
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div role="radiogroup" aria-label="Estado" className="inline-flex rounded-full border p-0.5">
        {modes.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={filterMode === value}
            onClick={() => onFilterModeChange(value)}
            className={cn(
              "h-7 rounded-full px-3 text-xs font-medium tabular-nums transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              filterMode === value
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        Mostrar
        <select
          value={subset}
          onChange={(e) => onSubsetChange(e.target.value as StudentSubset)}
          className={cn(
            "h-8 rounded-md border bg-background px-2 text-xs text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out focus:border-sena-green focus:ring-2 focus:ring-ring/30",
            subset !== "todos" ? "border-primary" : "border-input",
          )}
        >
          {SUBSETS.map((s) => (
            <option key={s} value={s} disabled={s !== "todos" && counts.subsets[s] === 0}>
              {SUBSET_LABELS[s]}
              {s !== "todos" ? ` (${counts.subsets[s]})` : ""}
            </option>
          ))}
        </select>
      </label>

      <div className="relative ml-auto min-w-[14rem] flex-1 sm:max-w-sm">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
        />
        <input
          type="text"
          placeholder="Buscar por nombre, cédula o correo"
          aria-label="Buscar aprendiz"
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-3 text-xs text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground/70 focus:border-sena-green focus:ring-2 focus:ring-ring/30"
        />
      </div>
    </div>
  );
}
