"use client";

import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { resultadoColor, resultadoLabel } from "./rap-status-badge";
import { parseRap, sortStudents, filterStudents } from "@/lib/grading";
import type { SortOption, FilterOption } from "@/lib/grading";
import { buildRapHeatmapPdfHtml } from "@/lib/pdf/rap-heatmap-pdf";
import type { StudentCrossResult } from "@/types/api";
import { FileDown } from "lucide-react";

const CELL_SIZE = 18;
const GAP = 1;
const NAME_WIDTH = 190;

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "name_asc", label: "Nombre A-Z" },
  { value: "name_desc", label: "Nombre Z-A" },
  { value: "listos_desc", label: "Más listos para aprobar" },
  { value: "pendientes_desc", label: "Más pendientes" },
  { value: "problemas_desc", label: "Más problemas" },
];

const FILTER_OPTIONS: { value: FilterOption; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "matricula_activa", label: "Matrícula activa" },
  { value: "matricula_cancelada", label: "Matrícula cancelada" },
  { value: "con_listos", label: "Con listos para aprobar" },
  { value: "con_problemas", label: "Con problemas" },
  { value: "con_inconsistencias", label: "Con inconsistencias" },
  { value: "todo_pendiente", label: "Todo pendiente" },
];

interface RapHeatmapProps {
  students: StudentCrossResult[];
  ficha?: string;
  courseName?: string;
}

export function RapHeatmap({ students, ficha, courseName }: RapHeatmapProps) {
  const [sortBy, setSortBy] = useState<SortOption>("name_asc");
  const [filterBy, setFilterBy] = useState<FilterOption>("all");
  const [includeDetailInPDF, setIncludeDetailInPDF] = useState(true);
  // Tooltip imperativo por delegación — evita re-renderizar toda la grilla
  // (~46×35 celdas) en cada movimiento del mouse (ver heatmap.tsx).
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  // Excluded RAP columns - persisted per ficha
  const [excludedRaps, setExcludedRaps] = useState<Set<number>>(() => {
    try {
      const saved = localStorage.getItem(`juicios-excluded-raps-${ficha}`);
      if (saved) return new Set(JSON.parse(saved) as number[]);
    } catch { /* ignore */ }
    return new Set();
  });

  // Excluded students - persisted per ficha
  const [excludedStudentIds, setExcludedStudentIds] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(`juicios-excluded-students-${ficha}`);
      if (saved) return new Set(JSON.parse(saved) as string[]);
    } catch { /* ignore */ }
    return new Set();
  });

  // Persist excluded RAPs
  useEffect(() => {
    const key = `juicios-excluded-raps-${ficha}`;
    if (excludedRaps.size === 0) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(Array.from(excludedRaps)));
  }, [excludedRaps, ficha]);

  // Persist excluded students
  useEffect(() => {
    const key = `juicios-excluded-students-${ficha}`;
    if (excludedStudentIds.size === 0) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(Array.from(excludedStudentIds)));
  }, [excludedStudentIds, ficha]);

  const toggleRap = useCallback((index: number) => {
    setExcludedRaps((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }, []);

  const toggleStudent = useCallback((name: string) => {
    setExcludedStudentIds((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const processed = useMemo(
    () => filterStudents(sortStudents(students, sortBy), filterBy),
    [students, sortBy, filterBy],
  );

  // Collect unique RAP names from first student (all should have same RAPs)
  const rapNames = useMemo(
    () => students[0]?.raps.map((r) => r.rap) ?? [],
    [students],
  );
  const rapParsed = useMemo(() => rapNames.map(parseRap), [rapNames]);

  // Delegación del hover (ver comentario del tooltipRef)
  const handleCellHover = (e: React.MouseEvent) => {
    const tip = tooltipRef.current;
    if (!tip) return;
    const cell = (e.target as HTMLElement).closest<HTMLElement>("[data-si]");
    if (!cell) {
      tip.style.display = "none";
      return;
    }
    const student = processed[Number(cell.dataset.si)];
    const ri = Number(cell.dataset.ri);
    const rap = rapNames[ri];
    const parsed = rapParsed[ri];
    if (!student || !parsed) {
      tip.style.display = "none";
      return;
    }
    const result = student.raps.find((r) => r.rap === rap);
    tip.textContent = result
      ? `${student.full_name}\nRAP ${parsed.number}: ${parsed.description.substring(0, 60)}...\nEstado: ${resultadoLabel(result.resultado)}\nEvidencias: ${result.evidencias_aprobadas}/${result.evidencias_total}`
      : `${student.full_name}\nRAP ${parsed.number}`;
    tip.style.left = `${e.clientX + 12}px`;
    tip.style.top = `${e.clientY - 10}px`;
    tip.style.display = "block";
  };

  const hideTooltip = () => {
    if (tooltipRef.current) tooltipRef.current.style.display = "none";
  };

  const handleExportPDF = useCallback(() => {
    const filterLabel = filterBy !== "all"
      ? ` (${FILTER_OPTIONS.find((o) => o.value === filterBy)?.label ?? ""})`
      : "";

    // Filter RAPs for PDF (exclude unchecked)
    const pdfRapIndices = rapNames.map((_, i) => i).filter((i) => !excludedRaps.has(i));
    const pdfRapNames = pdfRapIndices.map((i) => rapNames[i]);
    const pdfRapParsed = pdfRapIndices.map((i) => rapParsed[i]);

    // Filter students for PDF
    const studentsForPDF = processed.filter((s) => !excludedStudentIds.has(s.full_name));

    // Build detail list per student
    const detailByStudent = studentsForPDF.map((student) => {
      const rapLookup = new Map(student.raps.map((r) => [r.rap, r]));
      const issues: { rap: string; estado: string }[] = [];
      for (const rapName of pdfRapNames) {
        const result = rapLookup.get(rapName);
        if (result && result.resultado !== "correcto" && result.resultado !== "listo_para_aprobar") {
          const parsed = parseRap(rapName);
          issues.push({
            rap: `${parsed.code}-${parsed.number}`,
            estado: resultadoLabel(result.resultado),
          });
        }
      }
      return { name: student.full_name, issues };
    });

    const html = buildRapHeatmapPdfHtml({
      ficha,
      courseName,
      filterLabel,
      totalStudents: students.length,
      students: studentsForPDF,
      rapNames: pdfRapNames,
      rapParsed: pdfRapParsed,
      detailByStudent,
      includeDetail: includeDetailInPDF,
    });

    const printWindow = window.open("", "_blank");
    if (!printWindow) return;

    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.onload = () => {
      printWindow.print();
    };
  }, [processed, rapNames, rapParsed, students, ficha, courseName, filterBy, includeDetailInPDF, excludedRaps, excludedStudentIds]);

  if (students.length === 0) {
    return (
      <div className="rounded-xl border bg-card shadow-card p-8 text-center text-sm text-muted-foreground">
        No hay datos para mostrar el heatmap.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-3 rounded-[3px] bg-info" /> Listo para Aprobar
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-3 rounded-[3px] bg-ok" /> Correcto
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-3 rounded-[3px] bg-pending" /> Pendiente
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-3 rounded-[3px] bg-warn" /> Con Problemas
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-3 rounded-[3px] bg-danger" /> Inconsistencia
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-3 rounded-[3px] bg-notice" /> Aprobado Anticipado
        </span>
      </div>

      {/* Controls: Sort + Filter + Export */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor="heatmap-sort" className="text-xs font-medium text-muted-foreground">Ordenar:</label>
          <select
            id="heatmap-sort"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="h-8 cursor-pointer rounded-md border border-input bg-background px-2 text-xs text-foreground transition-[border-color,box-shadow] duration-150 ease-out focus:border-sena-green focus:outline-none focus:ring-2 focus:ring-ring/30"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5">
          <label htmlFor="heatmap-filter" className="text-xs font-medium text-muted-foreground">Aprendices:</label>
          <select
            id="heatmap-filter"
            value={filterBy}
            onChange={(e) => setFilterBy(e.target.value as FilterOption)}
            className="h-8 cursor-pointer rounded-md border border-input bg-background px-2 text-xs text-foreground transition-[border-color,box-shadow] duration-150 ease-out focus:border-sena-green focus:outline-none focus:ring-2 focus:ring-ring/30"
          >
            {FILTER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <span className="ml-auto text-xs tabular-nums text-muted-foreground">
          {processed.length} de {students.length} aprendices
        </span>

        {excludedStudentIds.size > 0 && (
          <span className="text-xs tabular-nums text-muted-foreground">
            PDF: {processed.length - excludedStudentIds.size}/{processed.length} apr.
            <button
              onClick={() => setExcludedStudentIds(new Set())}
              className="ml-1 cursor-pointer font-medium text-sena-green-dark transition-colors duration-150 ease-out hover:underline dark:text-sena-green"
            >
              todos
            </button>
          </span>
        )}
        {excludedRaps.size > 0 && (
          <span className="text-xs tabular-nums text-muted-foreground">
            PDF: {rapNames.length - excludedRaps.size}/{rapNames.length} RAPs
            <button
              onClick={() => setExcludedRaps(new Set())}
              className="ml-1 cursor-pointer font-medium text-sena-green-dark transition-colors duration-150 ease-out hover:underline dark:text-sena-green"
            >
              todas
            </button>
          </span>
        )}
        <label className="flex cursor-pointer select-none items-center gap-1.5 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={includeDetailInPDF}
            onChange={(e) => setIncludeDetailInPDF(e.target.checked)}
            className="rounded border-input accent-sena-green"
          />
          Incluir detalle
        </label>
        <Button
          variant="outline"
          size="sm"
          pill
          onClick={handleExportPDF}
        >
          <FileDown aria-hidden="true" className="h-3.5 w-3.5" />
          Exportar PDF
        </Button>
      </div>

      {/* Alternativa accesible: la misma información en formato tabla */}
      <p className="sr-only">
        Mapa de calor por color. La misma información está disponible en formato
        de tabla en las pestañas «Por aprendiz» y «Por RAP».
      </p>

      <div
        className="relative overflow-auto rounded-xl border bg-card shadow-card"
        onMouseOver={handleCellHover}
        onMouseLeave={hideTooltip}
        // Táctil: no hay hover — un tap sobre la celda fija el tooltip,
        // un tap fuera (o hacer scroll) lo oculta.
        onClick={handleCellHover}
        onScroll={hideTooltip}
      >
        <div className="relative" style={{ minWidth: rapNames.length * (CELL_SIZE + GAP) + NAME_WIDTH + 30 }}>
          {/* Column selection row */}
          <div className="flex items-center" style={{ height: CELL_SIZE + GAP, marginBottom: 2 }}>
            <div className="sticky left-0 z-10 w-[150px] sm:w-[210px] flex-shrink-0 bg-card pr-2 flex items-center">
              <button
                onClick={() => setExcludedStudentIds(new Set())}
                className="cursor-pointer px-1 py-1.5 text-[11px] font-medium leading-none text-sena-green-dark hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-sena-green"
                title="Incluir todos los aprendices en el PDF"
              >
                todos
              </button>
              <span className="text-[11px] text-muted-foreground" aria-hidden>|</span>
              <button
                onClick={() => setExcludedStudentIds(new Set(processed.map((s) => s.full_name)))}
                className="cursor-pointer px-1 py-1.5 text-[11px] font-medium leading-none text-sena-green-dark hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-sena-green"
                title="Excluir todos los aprendices del PDF"
              >
                ning.
              </button>
              <span className="mx-0.5 text-[11px] text-muted-foreground" aria-hidden>·</span>
              <button
                onClick={() => setExcludedRaps(new Set())}
                className="cursor-pointer px-1 py-1.5 text-[11px] font-medium leading-none text-sena-green-dark hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-sena-green"
                title="Seleccionar todas las RAPs"
              >
                todas
              </button>
              <span className="text-[11px] text-muted-foreground" aria-hidden>|</span>
              <button
                onClick={() => setExcludedRaps(new Set(rapNames.map((_, i) => i)))}
                className="cursor-pointer px-1 py-1.5 text-[11px] font-medium leading-none text-sena-green-dark hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-sena-green"
                title="Deseleccionar todas las RAPs"
              >
                ninguna
              </button>
            </div>
            <div className="flex gap-px">
              {rapNames.map((_, i) => {
                const parsed = rapParsed[i];
                const excluded = excludedRaps.has(i);
                return (
                  <button
                    key={`sel-${i}`}
                    type="button"
                    style={{ width: CELL_SIZE, height: CELL_SIZE }}
                    className={`flex-shrink-0 rounded-[2px] cursor-pointer border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                      excluded
                        ? "bg-danger-soft border-danger"
                        : "bg-ok-soft border-ok"
                    }`}
                    aria-pressed={!excluded}
                    aria-label={`RAP ${parsed?.code}-${parsed?.number} en el PDF`}
                    title={`RAP ${parsed?.number}: clic para ${excluded ? "incluir en" : "excluir de"} el PDF`}
                    onClick={() => toggleRap(i)}
                  />
                );
              })}
            </div>
          </div>
          {/* Student rows */}
          {processed.map((student, si) => {
            const isSuspended = student.status === "Suspendido";
            const isExcluded = excludedStudentIds.has(student.full_name);
            const rapLookup = new Map(student.raps.map((r) => [r.rap, r]));
            return (
              <div
                key={student.document}
                className="flex items-center"
                style={{
                  height: CELL_SIZE + GAP,
                  opacity: isSuspended ? 0.45 : 1,
                  // Virtualización ligera: omite layout/paint fuera del viewport
                  contentVisibility: "auto",
                  containIntrinsicSize: `auto ${CELL_SIZE + GAP}px`,
                }}
              >
                <div
                  className={`sticky left-0 z-10 w-[150px] sm:w-[210px] flex-shrink-0 flex items-center gap-1 bg-card pr-2 text-xs ${isSuspended ? "line-through text-muted-foreground" : ""}`}
                >
                  <button
                    type="button"
                    onClick={() => toggleStudent(student.full_name)}
                    style={{ width: CELL_SIZE - 2, height: CELL_SIZE - 2, minWidth: CELL_SIZE - 2 }}
                    className={`rounded-[2px] cursor-pointer border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                      isExcluded
                        ? "bg-danger-soft border-danger"
                        : "bg-ok-soft border-ok"
                    }`}
                    aria-pressed={!isExcluded}
                    aria-label={`${student.full_name} en el PDF`}
                    title={`${student.full_name} — clic para ${isExcluded ? "incluir" : "excluir"} del PDF`}
                  />
                  <span className="truncate" title={`${student.full_name}${isSuspended ? " (Suspendido)" : ""}`}>
                    {student.full_name}
                  </span>
                </div>
                <div className="flex gap-px">
                  {rapNames.map((rap, ri) => {
                    const result = rapLookup.get(rap);
                    const color = result ? resultadoColor(result.resultado) : "bg-pending-soft";
                    const parsed = rapParsed[ri];
                    return (
                      <div
                        key={rap}
                        data-si={si}
                        data-ri={ri}
                        role="img"
                        aria-label={`RAP ${parsed?.number}: ${result ? resultadoLabel(result.resultado) : "sin datos"}`}
                        style={{ width: CELL_SIZE, height: CELL_SIZE }}
                        className={`flex-shrink-0 rounded-[2px] cursor-pointer ${color} flex items-center justify-center`}
                      >
                        {/* Marca no cromática del estado que exige acción (WCAG 1.4.1) */}
                        {result?.resultado === "inconsistencia" && (
                          <span aria-hidden className="text-[10px] font-bold leading-none text-white">!</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
          {processed.length === 0 && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No hay aprendices con el filtro seleccionado
            </div>
          )}
        </div>

        {/* Tooltip imperativo (posicionado por handleCellHover, sin re-renders) */}
        <div
          ref={tooltipRef}
          style={{ display: "none" }}
          className="pointer-events-none fixed z-50 whitespace-pre-line rounded-md bg-foreground px-3 py-2 text-xs text-background shadow-lg"
        />
      </div>
    </div>
  );
}
