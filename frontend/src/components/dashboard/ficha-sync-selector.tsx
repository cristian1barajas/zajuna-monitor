"use client";

/**
 * Selección múltiple de fichas para sincronizarlas en un SOLO job.
 *
 * El scraper usa una única sesión Zajuna por job, así que actualizar varias
 * fichas se hace lanzando un job con todas ellas (secuencial, sin conflictos
 * de sesión), en lugar de varios jobs concurrentes.
 */

import { useMemo, useState } from "react";
import { CheckSquare, X } from "lucide-react";
import { FICHA_GRID, FichaCard } from "./ficha-card";
import { SyncButton } from "@/components/layout/sync-button";
import { useToGradeCounts } from "@/components/layout/use-to-grade";
import { cn } from "@/lib/utils";
import type { AlertItem, FichaSummaryItem } from "@/types/api";

interface FichaSyncSelectorProps {
  fichas: FichaSummaryItem[];
  alerts: AlertItem[];
}

const NO_ALERTS: AlertItem[] = [];

export function FichaSyncSelector({ fichas, alerts }: FichaSyncSelectorProps) {
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const toGrade = useToGradeCounts(fichas.map((f) => f.ficha));
  const alertsByFicha = useMemo(() => {
    const map = new Map<string, AlertItem[]>();
    for (const a of alerts) map.set(a.ficha, [...(map.get(a.ficha) ?? []), a]);
    return map;
  }, [alerts]);

  const toggle = (ficha: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ficha)) next.delete(ficha);
      else next.add(ficha);
      return next;
    });
  };

  const exitSelection = () => {
    setSelecting(false);
    setSelected(new Set());
  };

  const allSelected = selected.size === fichas.length && fichas.length > 0;
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(fichas.map((f) => f.ficha)));

  return (
    <div className="space-y-3">
      {/* Barra de control */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-foreground">
          {selecting ? (
            `${selected.size} ${selected.size === 1 ? "seleccionada" : "seleccionadas"}`
          ) : (
            <>
              Fichas{" "}
              <span className="font-normal tabular-nums text-muted-foreground">
                {fichas.length}
              </span>
            </>
          )}
        </h2>
        {selecting ? (
          <div className="flex items-center gap-2">
            <button
              onClick={toggleAll}
              className="rounded-md border px-3 py-1.5 text-xs font-medium transition-colors duration-150 ease-out hover:bg-accent hover:text-accent-foreground"
            >
              {allSelected ? "Ninguna" : "Todas"}
            </button>
            <button
              onClick={exitSelection}
              className="flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors duration-150 ease-out hover:bg-accent hover:text-accent-foreground"
            >
              <X className="h-3.5 w-3.5" />
              Cancelar
            </button>
          </div>
        ) : (
          <button
            onClick={() => setSelecting(true)}
            className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors duration-150 ease-out hover:bg-accent hover:text-accent-foreground"
          >
            <CheckSquare className="h-3.5 w-3.5" />
            Sincronizar varias
          </button>
        )}
      </div>

      {/* Lista densa de fichas */}
      {fichas.length > 0 ? (
        <div className="divide-y overflow-hidden rounded-xl border bg-card shadow-card">
          {/* Cabecera de columnas (desde md; en móvil cada fila trae su resumen) */}
          <div
            className={cn(
              "hidden bg-table-head px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground",
              FICHA_GRID,
            )}
          >
            <span>Ficha</span>
            <span className="text-right">Activos</span>
            <span className="text-right">Sin nota</span>
            <span className="text-right">Por calificar</span>
            <span className="text-right">Alertas</span>
            <span>Avance</span>
            <span />
          </div>
          {fichas.map((f) => (
            <FichaCard
              key={f.ficha}
              ficha={f}
              alerts={alertsByFicha.get(f.ficha) ?? NO_ALERTS}
              toGrade={toGrade.get(f.ficha) ?? null}
              selectable={selecting}
              selected={selected.has(f.ficha)}
              onToggleSelect={toggle}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          Sin fichas visibles. Actívalas con el ojo de la barra lateral o
          sincroniza para traer datos.
        </div>
      )}

      {/* Barra de acción flotante: anclada a la izquierda del contenido para no
          tapar el aviso de progreso de sincronización (abajo a la derecha) */}
      {selecting && selected.size > 0 && (
        <div className="fixed bottom-6 left-4 z-40 animate-in slide-in-from-bottom-4 fade-in duration-300 lg:left-[calc(var(--sidebar-w,16rem)+1.5rem)]">
          <div className="flex items-center gap-3 rounded-lg border bg-popover/95 px-4 py-3 text-popover-foreground shadow-xl backdrop-blur-sm">
            <span className="text-sm font-medium tabular-nums">
              {selected.size} ficha{selected.size > 1 ? "s" : ""} lista
              {selected.size > 1 ? "s" : ""} para sincronizar
            </span>
            <SyncButton
              fichas={[...selected]}
              label={`Sincronizar ${selected.size}`}
              onComplete={() => window.location.reload()}
            />
          </div>
        </div>
      )}
    </div>
  );
}
