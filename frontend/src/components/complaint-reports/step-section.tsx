"use client";

import { Check } from "lucide-react";
import { StepBadge } from "@/components/ui/step-badge";
import { cn } from "@/lib/utils";

interface StepSectionProps {
  n: number;
  title: string;
  /** Paso abierto: muestra su contenido completo. */
  active: boolean;
  /** Paso ya resuelto: muestra un check en lugar del número. */
  done: boolean;
  /** Resumen de una línea cuando el paso está cerrado. */
  summary?: React.ReactNode;
  /** Vuelve a abrir el paso; sin él, el paso cerrado no se puede editar todavía. */
  onEdit?: () => void;
  children: React.ReactNode;
}

/**
 * Paso de un flujo guiado a todo el ancho: solo el paso actual se despliega
 * y los demás quedan como una línea con su resumen.
 */
export function StepSection({ n, title, active, done, summary, onEdit, children }: StepSectionProps) {
  return (
    <section
      aria-current={active ? "step" : undefined}
      className={cn(
        "overflow-hidden rounded-xl border bg-card shadow-card",
        active && "border-primary/60",
      )}
    >
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        {done && !active ? (
          <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Check aria-hidden="true" className="h-3.5 w-3.5" />
            <span className="sr-only">Paso {n} listo</span>
          </span>
        ) : (
          <StepBadge n={n} className={cn(!active && "bg-muted text-muted-foreground")} />
        )}
        <h3 className={cn("text-sm font-semibold", active ? "text-foreground" : "text-muted-foreground")}>
          {title}
        </h3>
        {!active && summary && (
          <span className="min-w-0 flex-1 truncate text-sm text-foreground">{summary}</span>
        )}
        {!active && onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="ml-auto rounded-md px-2 py-1 text-xs font-medium text-sena-green-dark hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-sena-green"
          >
            Editar
          </button>
        )}
      </div>
      {active && <div className="border-t">{children}</div>}
    </section>
  );
}
