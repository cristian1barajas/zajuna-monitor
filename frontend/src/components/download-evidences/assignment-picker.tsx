"use client";

import { useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { compareGuides, guideOf } from "@/lib/pending-grading";
import type { AssignmentMapping } from "@/types/api";

interface AssignmentPickerProps {
  assignments: AssignmentMapping[];
  selectedCmid: number | null;
  onSelect: (cmid: number | null) => void;
  onLoad: () => void;
  loading: boolean;
}

const NO_GUIDE = "Otras evidencias";

/** Agrupa por guía (GA1, GA2…) en orden natural; lo que no trae guía va al final. */
function groupByGuide(assignments: AssignmentMapping[]): [string, AssignmentMapping[]][] {
  const groups = new Map<string, AssignmentMapping[]>();
  for (const a of assignments) {
    const key = guideOf(a.name) ?? NO_GUIDE;
    groups.set(key, [...(groups.get(key) ?? []), a]);
  }
  return [...groups.entries()].sort(([a], [b]) =>
    a === NO_GUIDE ? 1 : b === NO_GUIDE ? -1 : compareGuides(a, b),
  );
}

/** Buscador + lista desplegable agrupada por guía + "Ver envíos", en una sola fila. */
export function AssignmentPicker({
  assignments,
  selectedCmid,
  onSelect,
  onLoad,
  loading,
}: AssignmentPickerProps) {
  const [query, setQuery] = useState("");

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    // La tarea elegida se mantiene en la lista aunque no coincida con la búsqueda
    const visible = q
      ? assignments.filter((a) => a.cmid === selectedCmid || a.name.toLowerCase().includes(q))
      : assignments;
    return groupByGuide(visible);
  }, [assignments, query, selectedCmid]);

  const matches = groups.reduce((sum, [, items]) => sum + items.length, 0);

  return (
    <section className="flex flex-wrap items-center gap-2 rounded-xl border bg-card p-4 shadow-card">
      <div className="relative w-full sm:w-80">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar tarea"
          aria-label="Buscar tarea"
          className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground/70 focus:border-sena-green focus:ring-2 focus:ring-ring/30"
        />
      </div>
      <select
        value={selectedCmid ?? ""}
        onChange={(e) => onSelect(e.target.value ? Number(e.target.value) : null)}
        aria-label="Tarea"
        className="h-9 min-w-0 flex-1 basis-64 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out focus:border-sena-green focus:ring-2 focus:ring-ring/30"
      >
        <option value="">
          {matches === 0
            ? "Ninguna tarea coincide con la búsqueda"
            : `Elige una tarea (${matches} de ${assignments.length})`}
        </option>
        {groups.map(([guide, items]) => (
          <optgroup key={guide} label={guide}>
            {items.map((a) => (
              <option key={a.cmid} value={a.cmid}>
                {a.name}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      <Button onClick={onLoad} disabled={!selectedCmid || loading}>
        {loading ? <Loader2 aria-hidden="true" className="animate-spin" /> : <Search aria-hidden="true" />}
        Ver envíos
      </Button>
    </section>
  );
}
