"use client";

import { useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CronogramaEntry, EvidenceItem } from "@/types/api";

interface CronogramaTimelineProps {
  ficha: string;
  entries: CronogramaEntry[];
  /** Evidencias de Zajuna: dan el nombre legible y los conteos de notas. */
  evidences: EvidenceItem[];
}

const CODE_RE = /GA(\d+)-(\d{9})-AA\d+-EV\d+/;

// Un color por competencia para las que tienen cortes más cerca de hoy, que
// son las que el instructor tiene a la vista; las demás van en gris.
const PALETTE = [
  "var(--chart-1)",
  "var(--chart-4)",
  "var(--chart-3)",
  "var(--chart-5)",
  "var(--chart-2)",
];
const OTHER_COLOR = "var(--muted-foreground)";

type Status = "closed" | "soon" | "upcoming";

interface Item {
  code: string;
  competency: string | null;
  title: string;
  evidence: EvidenceItem | null;
}

interface CutoffGroup {
  date: string;
  status: Status;
  items: Item[];
}

function parseDate(date: string): Date {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function todayIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function daysBetween(from: string, to: string): number {
  return Math.round(
    (parseDate(to).getTime() - parseDate(from).getTime()) / 86_400_000
  );
}

function relativeLabel(days: number): string | null {
  if (days === 0) return "Hoy";
  if (days === 1) return "Mañana";
  if (days === -1) return "Ayer";
  if (days > 0 && days <= 14) return `En ${days} días`;
  if (days < 0 && days >= -14) return `Hace ${-days} días`;
  return null;
}

/** "Maquetación de la interfaz gráfica en HTML. GA5-…-EV04." → "Maquetación de la interfaz gráfica en HTML" */
function titleOf(name: string): string {
  return name
    .replace(/\s*GA\d+-\d{9}-AA\d+-EV\d+\.?/g, "")
    .replace(/\s*calificaci[oó]n\s*$/i, "")
    .replace(/[.\s]+$/, "")
    .trim();
}

/**
 * Cronograma como línea de tiempo: un nodo por fecha de corte, agrupado
 * por mes, con la marca de hoy. Los cortes caen casi siempre el mismo día
 * de la semana, así que cada nodo equivale a una semana del cronograma.
 */
export function CronogramaTimeline({
  ficha,
  entries,
  evidences,
}: CronogramaTimelineProps) {
  const todayRef = useRef<HTMLDivElement>(null);
  const today = todayIso();

  const { months, colors, hasOthers, nextGroup, closedCount, upcomingCount } =
    useMemo(() => {
      const byId = new Map(evidences.map((e) => [e.item_id, e]));
      const byCode = new Map<string, EvidenceItem>();
      for (const e of evidences) {
        const code = e.name.replace(/\s/g, "").match(CODE_RE)?.[0];
        if (code) byCode.set(code, e);
      }

      const nearest = new Map<string, number>();
      const groups = new Map<string, Item[]>();
      for (const entry of [...entries].sort((a, b) =>
        a.cutoff_date.localeCompare(b.cutoff_date)
      )) {
        const match = entry.evidence_name.replace(/\s/g, "").match(CODE_RE);
        const code = match?.[0] ?? entry.evidence_name;
        const competency = match?.[2] ?? null;
        if (competency) {
          const distance = Math.abs(daysBetween(today, entry.cutoff_date));
          nearest.set(competency, Math.min(nearest.get(competency) ?? Infinity, distance));
        }
        const evidence =
          (entry.evidence_item_id != null
            ? byId.get(entry.evidence_item_id)
            : undefined) ??
          byCode.get(code) ??
          null;
        const item = {
          code,
          competency,
          title: evidence ? titleOf(evidence.name) || code : code,
          evidence,
        };
        groups.set(entry.cutoff_date, [
          ...(groups.get(entry.cutoff_date) ?? []),
          item,
        ]);
      }

      const colors = new Map(
        [...nearest.entries()]
          .sort((a, b) => a[1] - b[1])
          .slice(0, PALETTE.length)
          .map(([competency], i) => [competency, PALETTE[i]])
      );

      const all: CutoffGroup[] = [...groups.entries()].map(([date, items]) => {
        const days = daysBetween(today, date);
        return {
          date,
          items,
          status: days < 0 ? "closed" : days <= 7 ? "soon" : "upcoming",
        };
      });

      const months = new Map<string, CutoffGroup[]>();
      for (const group of all) {
        const key = group.date.slice(0, 7);
        months.set(key, [...(months.get(key) ?? []), group]);
      }

      return {
        months: [...months.entries()],
        colors,
        hasOthers: nearest.size > colors.size,
        nextGroup: all.find((g) => g.status !== "closed") ?? null,
        closedCount: all
          .filter((g) => g.status === "closed")
          .reduce((n, g) => n + g.items.length, 0),
        upcomingCount: all
          .filter((g) => g.status !== "closed")
          .reduce((n, g) => n + g.items.length, 0),
      };
    }, [entries, evidences, today]);

  // Abre centrada en hoy: lo que ya cerró queda arriba y lo que viene, abajo
  useEffect(() => {
    todayRef.current?.scrollIntoView({ block: "center" });
  }, []);

  const todayMarker = (
    <div
      ref={todayRef}
      className="relative flex items-center gap-3 py-3 pl-[6.75rem] sm:pl-[8.75rem]"
    >
      <span className="absolute left-[6rem] h-3 w-3 -translate-x-1/2 rounded-full bg-sena-green ring-4 ring-sena-green/20 sm:left-[8rem]" />
      <span className="h-px flex-1 bg-sena-green" />
      <span className="rounded-full bg-sena-green px-2.5 py-0.5 text-xs font-semibold text-white">
        Hoy ·{" "}
        {parseDate(today).toLocaleDateString("es-CO", {
          weekday: "long",
          day: "numeric",
          month: "short",
        })}
      </span>
    </div>
  );

  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-card">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b px-4 py-3">
        <div className="space-y-0.5">
          <p className="text-sm font-semibold text-foreground">
            {nextGroup
              ? `Próximo corte: ${parseDate(nextGroup.date).toLocaleDateString(
                  "es-CO",
                  {
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                  }
                )}`
              : "No quedan cortes por venir"}
            {nextGroup && (
              <span className="font-normal text-muted-foreground">
                {" "}
                · {nextGroup.items.length}{" "}
                {nextGroup.items.length === 1 ? "evidencia" : "evidencias"}
              </span>
            )}
          </p>
          <p className="text-xs tabular-nums text-muted-foreground">
            {closedCount} ya {closedCount === 1 ? "cerró" : "cerraron"} ·{" "}
            {upcomingCount} por venir
          </p>
        </div>
        {colors.size > 0 && (
          <ul
            aria-label="Competencias"
            className="flex flex-wrap gap-x-3 gap-y-1"
          >
            {[...colors.entries()].map(([competency, color]) => (
              <li
                key={competency}
                className="flex items-center gap-1.5 text-xs tabular-nums text-muted-foreground"
              >
                <span
                  aria-hidden="true"
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: color }}
                />
                {competency}
              </li>
            ))}
            {hasOthers && (
              <li className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span
                  aria-hidden="true"
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: OTHER_COLOR }}
                />
                Otras
              </li>
            )}
          </ul>
        )}
      </header>

      <div className="relative px-4 pb-6">
        {/* Riel vertical */}
        <span
          aria-hidden="true"
          className="absolute bottom-0 top-0 left-[7rem] w-px bg-muted-foreground/30 sm:left-[9rem]"
        />

        {months.map(([month, groups]) => (
          <div key={month}>
            <h3 className="relative z-10 pt-6 pb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <span className="bg-card pr-2">
                {parseDate(`${month}-01`).toLocaleDateString("es-CO", {
                  month: "long",
                  year: "numeric",
                })}
              </span>
            </h3>
            {groups.map((group) => {
              const showMarker = group.date === nextGroup?.date;
              const days = daysBetween(today, group.date);
              const relative = relativeLabel(days);
              return (
                <div key={group.date}>
                  {showMarker && days !== 0 && todayMarker}
                  <div className="relative grid grid-cols-[5.5rem_1fr] gap-x-4 py-2 sm:grid-cols-[7.5rem_1fr]">
                    <div className="pt-2 text-right">
                      <p
                        className={cn(
                          "text-sm font-semibold capitalize tabular-nums",
                          group.status === "closed"
                            ? "text-muted-foreground"
                            : "text-foreground"
                        )}
                      >
                        {parseDate(group.date).toLocaleDateString("es-CO", {
                          weekday: "short",
                          day: "numeric",
                        })}
                      </p>
                      {relative && (
                        <p
                          className={cn(
                            "text-xs",
                            group.status === "soon"
                              ? "font-medium text-warn-fg"
                              : "text-muted-foreground"
                          )}
                        >
                          {relative}
                        </p>
                      )}
                    </div>
                    <span
                      aria-hidden="true"
                      className={cn(
                        "absolute top-4 left-[6rem] h-2.5 w-2.5 -translate-x-1/2 rounded-full border-2 sm:left-[8rem]",
                        group.status === "closed" &&
                          "border-muted-foreground/40 bg-card",
                        group.status === "soon" &&
                          "border-warn-fg bg-warn-soft",
                        group.status === "upcoming" && "border-border bg-card"
                      )}
                    />
                    <ul className="grid gap-2 pl-3 sm:grid-cols-2 xl:grid-cols-3">
                      {group.items.map((item) => (
                        <TimelineCard
                          key={item.code}
                          ficha={ficha}
                          item={item}
                          status={group.status}
                          color={
                            item.competency
                              ? (colors.get(item.competency) ?? OTHER_COLOR)
                              : undefined
                          }
                        />
                      ))}
                    </ul>
                  </div>
                  {showMarker && days === 0 && todayMarker}
                </div>
              );
            })}
          </div>
        ))}
        {!nextGroup && todayMarker}
      </div>
    </section>
  );
}

function TimelineCard({
  ficha,
  item,
  status,
  color,
}: {
  ficha: string;
  item: Item;
  status: Status;
  color: string | undefined;
}) {
  const { evidence } = item;
  const total = evidence
    ? evidence.total_approved +
      evidence.total_disapproved +
      evidence.total_pending
    : 0;
  const approvedPct = total > 0 ? (evidence!.total_approved / total) * 100 : 0;
  const disapprovedPct =
    total > 0 ? (evidence!.total_disapproved / total) * 100 : 0;

  const body = (
    <>
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-0 w-1 rounded-l-lg"
        style={{ background: color ?? "var(--border)" }}
      />
      <p className="flex items-center justify-between gap-2 font-mono text-[11px] text-muted-foreground">
        <span className="truncate">{item.code}</span>
        {evidence && (
          <ArrowUpRight
            aria-hidden="true"
            className="h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity duration-150 group-hover:opacity-100"
          />
        )}
      </p>
      <p
        className={cn(
          "line-clamp-2 text-sm font-medium leading-snug",
          status === "upcoming" ? "text-muted-foreground" : "text-foreground"
        )}
      >
        {item.title}
      </p>
      {evidence ? (
        <div className="mt-auto space-y-1 pt-1">
          <div className="flex h-1 w-full overflow-hidden rounded-full bg-muted">
            <div className="bg-ok" style={{ width: `${approvedPct}%` }} />
            <div
              className="bg-danger"
              style={{ width: `${disapprovedPct}%` }}
            />
          </div>
          <p className="text-xs tabular-nums">
            {status === "closed" ? (
              evidence.total_pending > 0 ? (
                <span className="font-medium text-danger-fg">
                  {evidence.total_pending} sin nota
                </span>
              ) : (
                <span className="font-medium text-ok-fg">Todos con nota</span>
              )
            ) : evidence.total_approved + evidence.total_disapproved > 0 ? (
              <span className="text-muted-foreground">
                {evidence.total_approved + evidence.total_disapproved} ya{" "}
                {evidence.total_approved + evidence.total_disapproved === 1 ? "calificada" : "calificadas"}
              </span>
            ) : (
              // Antes del cierre, "sin nota" es lo normal: no es un pendiente
              <span className="text-muted-foreground">Aún no cierra</span>
            )}
          </p>
        </div>
      ) : (
        <p className="mt-auto pt-1 text-xs text-muted-foreground">
          No está en Zajuna
        </p>
      )}
    </>
  );

  const className = cn(
    "group relative flex h-full flex-col gap-1 overflow-hidden rounded-lg border bg-background py-2.5 pl-4 pr-3",
    status === "soon" && "border-warn-border bg-warn-soft/30"
  );

  return (
    <li>
      {evidence ? (
        <Link
          href={`/fichas/${ficha}/pendientes-calificar?q=${encodeURIComponent(item.code)}`}
          title="Ver en Por calificar"
          className={cn(
            className,
            "transition-[border-color,box-shadow] duration-150 ease-out hover:border-sena-green/60 hover:shadow-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          )}
        >
          {body}
        </Link>
      ) : (
        <div className={className}>{body}</div>
      )}
    </li>
  );
}
