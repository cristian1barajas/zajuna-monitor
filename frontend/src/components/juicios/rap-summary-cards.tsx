import { cn } from "@/lib/utils";
import type { RapStatus } from "./student-filters";

interface RapSummaryCardsProps {
  summary: Record<string, number>;
  totalRaps: number;
  totalStudents: number;
  /** Estado que filtra la tabla por aprendiz; null = sin filtro */
  activeStatus?: RapStatus | null;
  onSelectStatus?: (status: RapStatus | null) => void;
}

const KPIS: { status: RapStatus; label: string; activeClass: string }[] = [
  { status: "listo_para_aprobar", label: "Listos para aprobar", activeClass: "text-info-fg" },
  { status: "correcto", label: "Correctos", activeClass: "text-ok-fg" },
  { status: "pendiente", label: "Pendientes", activeClass: "text-pending-fg" },
  { status: "con_problemas", label: "Con problemas", activeClass: "text-warn-fg" },
  { status: "inconsistencia", label: "Inconsistencias", activeClass: "text-danger-fg" },
  { status: "aprobado_anticipado", label: "Aprobados anticipados", activeClass: "text-notice-fg" },
];

/**
 * Franja de KPIs del cruce de juicios: una sola superficie dividida por
 * reglas de 1px (mismo lenguaje que la franja del dashboard). El color
 * de cada cifra viene de la familia de estado y solo se enciende cuando
 * el conteo es mayor que cero. Cada cifra filtra la tabla por aprendiz
 * a quienes tienen algún RAP en ese estado; pulsar la activa lo quita.
 */
export function RapSummaryCards({ summary, activeStatus = null, onSelectStatus }: RapSummaryCardsProps) {
  return (
    <section
      aria-label="Resumen del cruce de juicios"
      className="overflow-hidden rounded-lg border bg-border"
    >
      <div className="grid grid-cols-2 gap-px sm:grid-cols-3 xl:grid-cols-6">
        {KPIS.map((kpi) => {
          const value = summary[kpi.status] ?? 0;
          const active = activeStatus === kpi.status;
          return (
            <div key={kpi.status} className="bg-card">
              <button
                type="button"
                aria-pressed={active}
                disabled={!onSelectStatus || (value === 0 && !active)}
                onClick={() => onSelectStatus?.(active ? null : kpi.status)}
                className={cn(
                  "block h-full w-full cursor-pointer px-4 py-3.5 text-left transition-colors duration-150 ease-out hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring disabled:cursor-default disabled:hover:bg-transparent",
                  active && "bg-accent ring-2 ring-inset ring-primary hover:bg-accent",
                )}
              >
                <span className="block text-xs text-muted-foreground">{kpi.label}</span>
                <span
                  className={cn(
                    "mt-1 block text-2xl font-bold tabular-nums tracking-tight",
                    value > 0 ? kpi.activeClass : "text-muted-foreground",
                  )}
                >
                  {value.toLocaleString()}
                </span>
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
