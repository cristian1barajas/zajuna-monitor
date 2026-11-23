"use client";

import { useState } from "react";
import { ChevronRight, Search } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { groupCourseRows, type CourseRow } from "@/lib/course-selection";

type View = "monitoreados" | "disponibles";

interface CoursePickerProps {
  rows: CourseRow[];
  selected: Set<number>;
  onToggle: (courseId: number) => void;
}

/**
 * Cursos Zajuna del instructor con selección por checkbox: buscador,
 * vista monitoreados/disponibles y los cursos sin ficha plegados al final.
 */
export function CoursePicker({ rows, selected, onToggle }: CoursePickerProps) {
  const [query, setQuery] = useState("");
  // La página es para agregar: abre en disponibles salvo que no quede ninguno
  const [view, setView] = useState<View>(() =>
    rows.some((r) => !r.tracked && r.ficha) ? "disponibles" : "monitoreados"
  );
  const { monitored, available, withoutFicha } = groupCourseRows(rows, query);
  const visible = view === "monitoreados" ? monitored : available;

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 border-b px-4 py-3">
        <div className="relative min-w-[12rem] flex-1">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por ficha o programa"
            aria-label="Buscar curso"
            className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground/70 focus:border-sena-green focus:ring-2 focus:ring-ring/30"
          />
        </div>
        <div role="radiogroup" aria-label="Qué cursos mostrar" className="inline-flex rounded-full border p-0.5">
          {(
            [
              ["monitoreados", `Monitoreados (${monitored.length})`],
              ["disponibles", `Disponibles (${available.length})`],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={view === value}
              onClick={() => setView(value)}
              className={cn(
                "h-7 rounded-full px-3 text-xs font-medium transition-colors duration-150 ease-out",
                view === value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {visible.length > 0 ? (
        <CourseList rows={visible} selected={selected} onToggle={onToggle} />
      ) : (
        <p className="px-4 py-6 text-sm text-muted-foreground">
          {query.trim()
            ? "Ningún curso coincide con la búsqueda."
            : view === "monitoreados"
              ? "Aún no monitoreas ningún grupo."
              : "Ya monitoreas todos tus grupos con ficha."}
        </p>
      )}

      {view === "disponibles" && withoutFicha.length > 0 && (
        <details className="group border-t">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-4 py-3 text-xs font-medium text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden">
            <ChevronRight
              aria-hidden="true"
              className="h-3.5 w-3.5 transition-transform duration-150 group-open:rotate-90"
            />
            {withoutFicha.length} {withoutFicha.length === 1 ? "curso sin ficha" : "cursos sin ficha"} · no se
            pueden monitorear
          </summary>
          <div className="border-t">
            <CourseList rows={withoutFicha} selected={selected} onToggle={onToggle} />
          </div>
        </details>
      )}
    </>
  );
}

function CourseList({ rows, selected, onToggle }: CoursePickerProps) {
  return (
    <ul className="divide-y" aria-label="Cursos de tu cuenta Zajuna">
      {rows.map((row) => (
        <CoursePickerRow
          key={row.course_id}
          row={row}
          checked={selected.has(row.course_id)}
          onToggle={() => onToggle(row.course_id)}
        />
      ))}
    </ul>
  );
}

function CoursePickerRow({
  row,
  checked,
  onToggle,
}: {
  row: CourseRow;
  checked: boolean;
  onToggle: () => void;
}) {
  const selectable = row.ficha !== "";
  const id = `course-${row.course_id}`;

  return (
    <li
      className={cn(
        "flex items-center gap-4 px-4 py-3 transition-colors duration-150 ease-out",
        selectable ? "hover:bg-muted/60" : "opacity-60",
        checked && "bg-accent hover:bg-accent"
      )}
    >
      <Checkbox
        id={id}
        checked={checked}
        disabled={!selectable}
        onCheckedChange={onToggle}
        className="shrink-0"
      />
      <label htmlFor={id} className={cn("min-w-0 flex-1", selectable && "cursor-pointer")}>
        <span className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold tracking-tight text-foreground">
            {row.ficha || "Sin ficha"}
          </span>
          {row.program_code && (
            <span className="rounded-full border border-notice-border bg-notice-soft px-2 py-0.5 text-[11px] font-semibold text-notice-fg">
              {row.program_label}
            </span>
          )}
        </span>
        <span className="block truncate text-xs text-muted-foreground" title={row.shortname}>
          {row.fullname}
          <span className="font-mono"> · curso {row.course_id}</span>
        </span>
      </label>
      <RowStatus row={row} checked={checked} />
    </li>
  );
}

function RowStatus({ row, checked }: { row: CourseRow; checked: boolean }) {
  if (!row.ficha) {
    return <span className="shrink-0 text-xs text-muted-foreground">No se puede monitorear</span>;
  }
  if (row.missing) {
    return (
      <span className="shrink-0 rounded-full border border-warn-border bg-warn-soft px-2 py-0.5 text-[11px] font-medium text-warn-fg">
        Ya no está en Mis cursos
      </span>
    );
  }
  if (row.tracked && checked) {
    return (
      <span className="shrink-0 rounded-full border border-ok-border bg-ok-soft px-2 py-0.5 text-[11px] font-medium text-ok-fg">
        Monitoreando
      </span>
    );
  }
  if (row.tracked && !checked) {
    return (
      <span className="shrink-0 rounded-full border border-danger-border bg-danger-soft px-2 py-0.5 text-[11px] font-medium text-danger-fg">
        Se dejará de monitorear
      </span>
    );
  }
  if (checked) {
    return (
      <span className="shrink-0 rounded-full border border-info-border bg-info-soft px-2 py-0.5 text-[11px] font-medium text-info-fg">
        Nuevo
      </span>
    );
  }
  return null;
}
