"use client";

import { useState } from "react";
import { Check, Loader2, Plus, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  SOPORTE_STAGES,
  dayParts,
  formatDay,
  stageInfo,
  type SendDate,
} from "./stages";

interface LlamadosFiltersProps {
  sendDates: SendDate[];
  extraDates: string[];
  selectedDates: Set<string>;
  selectedStages: Set<string>;
  canSearch: boolean;
  searching: boolean;
  onToggleDate: (date: string) => void;
  onAddDate: (date: string) => void;
  onRemoveExtraDate: (date: string) => void;
  onToggleStage: (stage: string) => void;
  onSearch: () => void;
}

/** Bloque tipo calendario con la fecha; marcado cuando la fecha está elegida. */
function DayBlock({ date, checked }: { date: string; checked: boolean }) {
  const p = dayParts(date);
  return (
    <span
      className={cn(
        "flex w-12 shrink-0 flex-col items-center rounded-lg border py-1 leading-none transition-colors duration-150",
        checked
          ? "border-primary bg-primary text-primary-foreground"
          : "bg-muted/40 text-foreground"
      )}
    >
      <span className="text-[10px] uppercase tracking-wide opacity-80">
        {p.weekday}
      </span>
      <span className="text-lg font-bold tabular-nums">{p.day}</span>
    </span>
  );
}

/** Panel de búsqueda: fechas exactas de envío (sugeridas por Debido proceso) y etapas. */
export function LlamadosFilters({
  sendDates,
  extraDates,
  selectedDates,
  selectedStages,
  canSearch,
  searching,
  onToggleDate,
  onAddDate,
  onRemoveExtraDate,
  onToggleStage,
  onSearch,
}: LlamadosFiltersProps) {
  const [newDate, setNewDate] = useState("");

  const addDate = () => {
    if (!newDate) return;
    onAddDate(newDate);
    setNewDate("");
  };

  const disabledReason = !canSearch
    ? "Conecta Outlook para buscar"
    : selectedDates.size === 0
      ? "Marca al menos una fecha"
      : selectedStages.size === 0
        ? "Marca al menos una etapa"
        : null;

  return (
    <section
      aria-labelledby="filtros-titulo"
      className="flex flex-col rounded-xl border bg-card shadow-card"
    >
      <div className="border-b px-4 py-3">
        <h2 id="filtros-titulo" className="text-sm font-semibold">
          ¿Qué correos buscar?
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Días en que registraste llamados en Debido proceso.
        </p>
      </div>

      <fieldset className="px-4 py-3">
        <legend className="sr-only">Fechas de envío</legend>
        {sendDates.length === 0 && extraDates.length === 0 && (
          <p className="mb-2 text-sm text-muted-foreground">
            No hay llamados registrados en este grupo; agrega la fecha a mano.
          </p>
        )}
        <ul className="space-y-1.5">
          {sendDates.map((d) => {
            const checked = selectedDates.has(d.date);
            const total = d.counts.reduce((n, c) => n + c.count, 0);
            return (
              <li key={d.date}>
                <button
                  type="button"
                  aria-pressed={checked}
                  onClick={() => onToggleDate(d.date)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg border px-2 py-2 text-left transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    checked
                      ? "border-primary/60 bg-accent"
                      : "hover:bg-muted/50"
                  )}
                >
                  <DayBlock date={d.date} checked={checked} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-medium capitalize">
                        {dayParts(d.date).month}
                      </span>
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {total} {total === 1 ? "llamado" : "llamados"}
                      </span>
                    </span>
                    <span className="mt-1 flex flex-wrap gap-x-2.5 gap-y-0.5">
                      {d.counts.map((c) => {
                        const s = stageInfo(c.stage);
                        return (
                          <span
                            key={c.stage}
                            className="inline-flex items-center gap-1 text-[11px] text-muted-foreground"
                          >
                            <span
                              aria-hidden="true"
                              className={cn(
                                "h-1.5 w-1.5 rounded-full",
                                s?.dot ?? "bg-muted-foreground"
                              )}
                            />
                            {s?.short ?? c.stage}{" "}
                            <span className="font-semibold tabular-nums text-foreground">
                              {c.count}
                            </span>
                          </span>
                        );
                      })}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
          {extraDates.map((date) => {
            const checked = selectedDates.has(date);
            return (
              <li key={date} className="flex items-center gap-1">
                <button
                  type="button"
                  aria-pressed={checked}
                  onClick={() => onToggleDate(date)}
                  className={cn(
                    "flex flex-1 items-center gap-3 rounded-lg border px-2 py-2 text-left transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    checked
                      ? "border-primary/60 bg-accent"
                      : "hover:bg-muted/50"
                  )}
                >
                  <DayBlock date={date} checked={checked} />
                  <span className="text-sm">
                    <span className="block font-medium capitalize">
                      {dayParts(date).month}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Agregada a mano
                    </span>
                  </span>
                </button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => onRemoveExtraDate(date)}
                  aria-label={`Quitar ${formatDay(date)}`}
                >
                  <X aria-hidden="true" />
                </Button>
              </li>
            );
          })}
        </ul>
        <div className="mt-2 flex items-center gap-2">
          <label htmlFor="otra-fecha" className="sr-only">
            Agregar otra fecha
          </label>
          <input
            id="otra-fecha"
            type="date"
            value={newDate}
            onChange={(e) => setNewDate(e.target.value)}
            className="h-8 min-w-0 flex-1 rounded-lg border bg-card px-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={addDate}
            disabled={!newDate}
          >
            <Plus aria-hidden="true" /> Otra fecha
          </Button>
        </div>
      </fieldset>

      <fieldset className="border-t px-4 py-3">
        <legend className="mb-2 px-0 text-xs font-semibold text-muted-foreground">
          Etapas
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {SOPORTE_STAGES.map((s) => {
            const on = selectedStages.has(s.key);
            return (
              <button
                key={s.key}
                type="button"
                aria-pressed={on}
                onClick={() => onToggleStage(s.key)}
                className={cn(
                  "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  on
                    ? "border-primary/60 bg-accent text-foreground"
                    : "text-muted-foreground hover:bg-muted/50"
                )}
              >
                {on ? (
                  <Check aria-hidden="true" className="h-3 w-3" />
                ) : (
                  <span
                    aria-hidden="true"
                    className={cn("h-1.5 w-1.5 rounded-full", s.dot)}
                  />
                )}
                {s.short}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="mt-auto border-t px-4 py-3">
        <Button
          className="w-full"
          onClick={onSearch}
          disabled={searching || disabledReason !== null}
        >
          {searching ? (
            <Loader2 aria-hidden="true" className="animate-spin" />
          ) : (
            <Search aria-hidden="true" />
          )}
          {searching
            ? "Buscando en Outlook…"
            : `Buscar en ${selectedDates.size} ${selectedDates.size === 1 ? "fecha" : "fechas"}`}
        </Button>
        {disabledReason && !searching && (
          <p className="mt-1.5 text-center text-xs text-muted-foreground">
            {disabledReason}
          </p>
        )}
      </div>
    </section>
  );
}
