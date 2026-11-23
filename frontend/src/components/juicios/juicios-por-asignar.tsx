"use client";

/**
 * Juicios por asignar en Sofía Plus. Sofía permite el cargue en grupo:
 * marcar aprendices, elegir competencia y RAP y asignar un valor. Aquí salen
 * esos grupos, uno por RAP, con los códigos de Sofía y los aprendices en
 * orden alfabético. "No aprobar" usa las evidencias elegidas hasta el corte
 * (la misma selección de Reportes): elegida y sin nota = no entregada.
 */

import { useEffect, useMemo, useState } from "react";
import { CircleCheck, CircleX, FileDown, ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EvidencePicker } from "@/components/evidences/evidence-picker";
import { fetchCronograma, fetchFichaDetail, postJuiciosPorAsignar } from "@/lib/api";
import { readEvidenceSelection, writeEvidenceSelection } from "@/lib/evidence-selection";
import { buildJuiciosPorAsignarPdfHtml, type JuiciosPdfLista } from "@/lib/pdf/juicios-por-asignar-pdf";
import { buildCutoffMap, compareGuides, guideOf } from "@/lib/pending-grading";
import { cn } from "@/lib/utils";
import type { CronogramaResponse, EvidenceItem, JuiciosPorAsignarResponse, RapPorAsignar } from "@/types/api";
import { RapAsignarCard, type AsignarModo } from "./rap-asignar-card";

const MARKS_KEY = "zajuna_juicios_marcados_";

function readMarks(ficha: string): Set<string> {
  try {
    const raw = localStorage.getItem(MARKS_KEY + ficha);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function formatDate(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

/** RAPs agrupados por competencia, en el orden que llegan (código del programa). */
function byCompetencia(raps: RapPorAsignar[]) {
  const groups: { key: string; first: RapPorAsignar; raps: RapPorAsignar[] }[] = [];
  for (const rap of raps) {
    const key = `${rap.competencia_code}|${rap.competencia_programa}`;
    const last = groups.at(-1);
    if (last && last.key === key) last.raps.push(rap);
    else groups.push({ key, first: rap, raps: [rap] });
  }
  return groups;
}

export function JuiciosPorAsignar({ ficha }: { ficha: string }) {
  const [evidences, setEvidences] = useState<EvidenceItem[]>([]);
  const [courseName, setCourseName] = useState("");
  const [cronograma, setCronograma] = useState<CronogramaResponse | null>(null);
  const [stored, setStored] = useState<Set<number>>(() => readEvidenceSelection(ficha));
  const [pickerOpen, setPickerOpen] = useState(false);
  const [data, setData] = useState<JuiciosPorAsignarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modo, setModo] = useState<AsignarModo>("aprobar");
  const [marks, setMarks] = useState<Set<string>>(() => readMarks(ficha));

  useEffect(() => {
    Promise.all([fetchFichaDetail(ficha), fetchCronograma(ficha).catch(() => null)])
      .then(([detail, crono]) => {
        setEvidences(detail.evidences);
        setCourseName(detail.course_name);
        setCronograma(crono);
      })
      .catch((e: Error) => setError(e.message));
  }, [ficha]);

  useEffect(() => writeEvidenceSelection(ficha, stored), [stored, ficha]);

  useEffect(() => {
    try {
      localStorage.setItem(MARKS_KEY + ficha, JSON.stringify([...marks]));
    } catch {
      /* sin almacenamiento local: las marcas viven solo en esta visita */
    }
  }, [marks, ficha]);

  // Solo cuentan las evidencias que siguen existiendo en el curso.
  const selected = useMemo(() => {
    const valid = new Set(evidences.map((e) => e.item_id));
    return new Set([...stored].filter((id) => valid.has(id)));
  }, [stored, evidences]);
  const selectedKey = [...selected].sort((a, b) => a - b).join(",");
  const cutoffs = useMemo(() => buildCutoffMap(cronograma), [cronograma]);

  useEffect(() => {
    if (evidences.length === 0) return;
    let cancelled = false;
    const ids = selectedKey ? selectedKey.split(",").map(Number) : [];
    postJuiciosPorAsignar(ficha, ids)
      .then((d) => !cancelled && setData(d))
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [ficha, selectedKey, evidences.length]);

  const summary = useMemo(() => {
    const chosen = evidences.filter((e) => selected.has(e.item_id));
    const guides = [...new Set(chosen.map((e) => guideOf(e.name)).filter((g): g is string => g !== null))].sort(
      compareGuides,
    );
    const lastCutoff = chosen
      .map((e) => cutoffs.get(e.item_id))
      .filter((d): d is string => Boolean(d))
      .sort()
      .at(-1);
    return {
      guides: guides.length > 4 ? `${guides[0]} a ${guides.at(-1)}` : guides.join(", "),
      lastCutoff,
    };
  }, [evidences, selected, cutoffs]);

  if (error) {
    return (
      <p className="rounded-lg border border-danger-border bg-danger-soft p-3 text-sm text-danger-fg">{error}</p>
    );
  }

  const corteText =
    selected.size === 0
      ? "sin selección (solo cuentan las evidencias con D)"
      : [
          `${selected.size} de ${evidences.length}`,
          summary.guides && `guías ${summary.guides}`,
          summary.lastCutoff && `corte ${formatDate(summary.lastCutoff)}`,
        ]
          .filter(Boolean)
          .join(" · ");

  // Mismo patrón que el heatmap: HTML en una ventana nueva y diálogo de impresión (Guardar como PDF).
  const printPdf = (lista: JuiciosPdfLista) => {
    if (!data) return;
    const html = buildJuiciosPorAsignarPdfHtml({
      ficha,
      courseName,
      data,
      lista,
      corte: corteText,
      isMarked: (lista, rapCode, doc) => marks.has(`${lista}|${rapCode}|${doc}`),
    });
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.onload = () => printWindow.print();
  };

  const raps = data ? data[modo] : [];
  const count = (list: RapPorAsignar[]) => list.reduce((n, r) => n + r.aprendices.length, 0);
  const markKey = (rap: RapPorAsignar, doc: string) => `${modo}|${rap.rap_code}|${doc}`;

  return (
    <div className="space-y-4">
      {/* Evidencias hasta el corte (compartidas con Reportes) */}
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4 shadow-card">
        <div className="min-w-0">
          <p className="text-sm text-foreground">
            <span className="font-semibold tabular-nums">{selected.size}</span> de{" "}
            <span className="tabular-nums">{evidences.length}</span> evidencias hasta el corte
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {selected.size === 0
              ? "Elige hasta dónde ya debían entregar: sin selección, solo cuentan las evidencias con D."
              : [
                  summary.guides && `Guías ${summary.guides}`,
                  summary.lastCutoff && `corte ${formatDate(summary.lastCutoff)}`,
                  "las elegidas sin nota cuentan como no entregadas",
                ]
                  .filter(Boolean)
                  .join(" · ")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setPickerOpen(true)} disabled={evidences.length === 0}>
            <ListChecks aria-hidden="true" />
            {selected.size === 0 ? "Elegir evidencias" : "Cambiar"}
          </Button>
          <Button variant="outline" onClick={() => printPdf("aprobar")} disabled={!data}>
            <FileDown aria-hidden="true" className="text-ok-fg" />
            PDF Aprobar
          </Button>
          <Button variant="outline" onClick={() => printPdf("no_aprobar")} disabled={!data}>
            <FileDown aria-hidden="true" className="text-danger-fg" />
            PDF No aprobar
          </Button>
        </div>
      </section>

      {/* Aprobar | No aprobar */}
      <div role="tablist" aria-label="Juicio a asignar" className="grid gap-3 sm:grid-cols-2">
        {(
          [
            { id: "aprobar", label: "Aprobar en Sofía", hint: "Todas las evidencias del RAP en A", icon: CircleCheck, tone: "text-ok-fg", ring: "border-ok-border bg-ok-soft" },
            { id: "no_aprobar", label: "No aprobar en Sofía", hint: "Alguna D o evidencia sin entregar hasta el corte", icon: CircleX, tone: "text-danger-fg", ring: "border-danger-border bg-danger-soft" },
          ] as const
        ).map((t) => {
          const active = modo === t.id;
          const list = data ? data[t.id] : [];
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setModo(t.id)}
              className={cn(
                "flex items-center gap-3 rounded-xl border p-4 text-left shadow-card transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active ? t.ring : "bg-card hover:bg-muted/50",
              )}
            >
              <Icon aria-hidden="true" className={cn("h-7 w-7 shrink-0", t.tone)} />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-foreground">{t.label}</span>
                <span className="block text-xs text-muted-foreground">{t.hint}</span>
              </span>
              <span className="shrink-0 text-right">
                <span className={cn("block text-2xl font-bold tabular-nums leading-none", t.tone)}>
                  {data ? count(list) : "–"}
                </span>
                <span className="text-[11px] tabular-nums text-muted-foreground">
                  {data ? `en ${list.length} RAP` : ""}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {data && data.fuera_de_formacion + data.con_novedad + data.suspendidos > 0 && (
        <p className="text-xs text-muted-foreground">
          No se listan:{" "}
          {[
            data.con_novedad > 0 && `${data.con_novedad} con novedad`,
            data.suspendidos > 0 && `${data.suspendidos} suspendidos en Zajuna`,
            data.fuera_de_formacion > 0 && `${data.fuera_de_formacion} que no están EN FORMACIÓN en Sofía`,
          ]
            .filter(Boolean)
            .join(" · ")}
          .
        </p>
      )}

      {loading || !data ? (
        <div className="space-y-3">
          <Skeleton className="h-28 rounded-lg" />
          <Skeleton className="h-28 rounded-lg" />
        </div>
      ) : raps.length === 0 ? (
        <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          {modo === "aprobar"
            ? "No hay aprendices con todas las evidencias de un RAP aprobadas y el juicio por evaluar."
            : "No hay aprendices para no aprobar con esta selección de evidencias."}
        </p>
      ) : (
        byCompetencia(raps).map((g) => (
          <section key={g.key} className="space-y-2">
            <header className="rounded-lg border-l-4 border-primary bg-card px-4 py-2.5 shadow-card">
              <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                <span className="font-semibold uppercase tracking-wide">Competencia</span>
                <span className="font-mono font-semibold tabular-nums text-foreground">{g.first.competencia_code}</span>
                {g.first.competencia_programa && (
                  <span className="tabular-nums">· programa {g.first.competencia_programa}</span>
                )}
              </p>
              <p className="mt-0.5 text-sm font-semibold leading-snug text-foreground">{g.first.competencia_desc}</p>
            </header>
            <div className="space-y-3 pl-0 sm:pl-4">
              {g.raps.map((rap) => (
                <RapAsignarCard
                  key={`${modo}-${rap.rap_code}-${rap.rap_programa}`}
                  rap={rap}
                  modo={modo}
                  checked={
                    new Set(rap.aprendices.map((a) => a.document).filter((d) => marks.has(markKey(rap, d))))
                  }
                  onToggle={(doc) =>
                    setMarks((m) => {
                      const next = new Set(m);
                      const k = markKey(rap, doc);
                      if (next.has(k)) next.delete(k);
                      else next.add(k);
                      return next;
                    })
                  }
                  onToggleAll={(docs, value) =>
                    setMarks((m) => {
                      const next = new Set(m);
                      for (const d of docs) {
                        if (value) next.add(markKey(rap, d));
                        else next.delete(markKey(rap, d));
                      }
                      return next;
                    })
                  }
                />
              ))}
            </div>
          </section>
        ))
      )}

      <EvidencePicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        evidences={evidences}
        selected={selected}
        onChange={setStored}
        cutoffs={cutoffs}
        title="Evidencias hasta el corte"
      />
    </div>
  );
}
