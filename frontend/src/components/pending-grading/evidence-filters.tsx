"use client";

import { DropdownMenu } from "radix-ui";
import { Check, ChevronDown, Search, X } from "lucide-react";
import {
  CLOSING_LABELS,
  KIND_LABELS,
  hasActiveFilters,
  type ClosingBucket,
  type EvidenceKind,
  type PendingFilters,
} from "@/lib/pending-grading";
import { cn } from "@/lib/utils";

interface EvidenceFiltersProps {
  filters: PendingFilters;
  onChange: (next: PendingFilters) => void;
  onClear: () => void;
  guides: string[];
  phases: string[];
  /** Sin cronograma cargado no tiene sentido filtrar por cierre. */
  hasCronograma: boolean;
  /** Sin mapeo de tareas/foros/cuestionarios, el filtro de tipo no aplica. */
  showKind?: boolean;
}

function toggle<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

interface MultiSelectProps<T extends string> {
  label: string;
  options: T[];
  selected: Set<T>;
  optionLabel?: (value: T) => string;
  onChange: (next: Set<T>) => void;
}

/** Menú desplegable con casillas: varias opciones por filtro en un solo botón. */
export function MultiSelect<T extends string>({
  label,
  options,
  selected,
  optionLabel = (v) => v,
  onChange,
}: MultiSelectProps<T>) {
  const chosen = options.filter((o) => selected.has(o));
  const summary =
    chosen.length === 0 ? null : chosen.length === 1 ? optionLabel(chosen[0]) : String(chosen.length);

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        className={cn(
          "inline-flex h-9 max-w-[14rem] items-center gap-1.5 rounded-md border px-3 text-sm transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          summary
            ? "border-primary bg-accent font-medium text-accent-foreground"
            : "border-input bg-background text-foreground hover:bg-accent",
        )}
      >
        <span className="min-w-0 truncate">
          {label}
          {summary && `: ${summary}`}
        </span>
        <ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={6}
          className="z-50 max-h-80 min-w-[12rem] overflow-y-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-lg"
        >
          {options.map((option) => (
            <DropdownMenu.CheckboxItem
              key={option}
              checked={selected.has(option)}
              onCheckedChange={() => onChange(toggle(selected, option))}
              // Mantener el menú abierto para marcar varias opciones seguidas
              onSelect={(e) => e.preventDefault()}
              className="flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
            >
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded border border-input">
                <DropdownMenu.ItemIndicator>
                  <Check aria-hidden="true" className="h-3 w-3" />
                </DropdownMenu.ItemIndicator>
              </span>
              {optionLabel(option)}
            </DropdownMenu.CheckboxItem>
          ))}
          {chosen.length > 0 && (
            <>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item
                onSelect={() => onChange(new Set())}
                className="cursor-pointer select-none rounded-md px-2 py-1.5 text-xs text-muted-foreground outline-none data-[highlighted]:bg-accent data-[highlighted]:text-foreground"
              >
                Quitar selección
              </DropdownMenu.Item>
            </>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

const KINDS: EvidenceKind[] = ["assign", "forum", "quiz"];
const CLOSINGS: ClosingBucket[] = ["vencida", "semana", "despues", "sin-fecha"];

export function EvidenceFilters({
  filters,
  onChange,
  onClear,
  guides,
  phases,
  hasCronograma,
  showKind = true,
}: EvidenceFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {guides.length > 0 && (
        <MultiSelect
          label="Guía"
          options={guides}
          selected={filters.guides}
          onChange={(guides) => onChange({ ...filters, guides })}
        />
      )}
      {phases.length > 1 && (
        <MultiSelect
          label="Fase"
          options={phases}
          selected={filters.phases}
          onChange={(phases) => onChange({ ...filters, phases })}
        />
      )}
      {showKind && (
        <MultiSelect
          label="Tipo"
          options={KINDS}
          selected={filters.kinds}
          optionLabel={(k) => KIND_LABELS[k]}
          onChange={(kinds) => onChange({ ...filters, kinds })}
        />
      )}
      {hasCronograma && (
        <MultiSelect
          label="Cierre"
          options={CLOSINGS}
          selected={filters.closing}
          optionLabel={(c) => CLOSING_LABELS[c]}
          onChange={(closing) => onChange({ ...filters, closing })}
        />
      )}

      {/* El buscador va después de los menús: así un menú abierto no se
          desplaza cuando su botón cambia de ancho al marcar opciones */}
      <div className="relative min-w-[12rem] flex-1">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
        <input
          type="text"
          placeholder="Buscar evidencia"
          aria-label="Buscar evidencia"
          value={filters.text}
          onChange={(e) => onChange({ ...filters, text: e.target.value })}
          className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground/70 focus:border-sena-green focus:ring-2 focus:ring-ring/30"
        />
      </div>

      {hasActiveFilters(filters) && (
        <button
          type="button"
          onClick={onClear}
          className="inline-flex h-9 items-center gap-1 rounded-md px-2 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X aria-hidden="true" className="h-3.5 w-3.5" />
          Limpiar filtros
        </button>
      )}
    </div>
  );
}
