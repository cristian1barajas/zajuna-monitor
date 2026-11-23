"use client";

import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { DropdownMenu } from "radix-ui";
import { Check, ChevronDown, FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { StudentItem, EvidenceItem } from "@/types/api";
import { checkSubmissionStatus, fetchNovedades } from "@/lib/api";
import { gradeColor, isLectiva, countGrades, extractGACode } from "@/lib/grading";
import { buildHeatmapPdfHtml } from "@/lib/pdf/heatmap-pdf";

interface HeatmapProps {
  students: StudentItem[];
  evidences: EvidenceItem[];
  ficha?: string;
  courseName?: string;
}

const CELL_SIZE = 18;
const GAP = 1;

type SortKey =
  | "name_asc"
  | "name_desc"
  | "mas_aprobadas"
  | "mas_pendientes"
  | "mas_desaprobadas";
type StudentFilterKey =
  | "all"
  | "matricula_activa"
  | "matricula_cancelada"
  | "con_actividad"
  | "sin_actividad"
  | "con_pendientes"
  | "todo_aprobado"
  | "con_desaprobadas"
  | "sin_novedad"
  | "con_novedad";
type EvidenceFilterKey = "all" | "lectiva" | "productiva";

export function Heatmap({ students, evidences, ficha, courseName }: HeatmapProps) {
  // Tooltip imperativo (fuera de React): con ~8.900 celdas, un estado de
  // tooltip en este componente re-renderizaba TODA la grilla en cada
  // movimiento del mouse. La grilla delega el hover al contenedor y este
  // ref se posiciona/escribe directo en el DOM — cero re-renders por hover.
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("name_asc");
  const [studentFilter, setStudentFilter] = useState<StudentFilterKey>("all");
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilterKey>("all");
  const [includeDetailInPDF, setIncludeDetailInPDF] = useState(true);
  // Las casillas para incluir/excluir del PDF solo se muestran cuando se piden
  const [pickForPdf, setPickForPdf] = useState(false);

  // Submitted-but-ungraded cells (yellow) - set of "item_id:user_id"
  const [pendingCells, setPendingCells] = useState<Set<string>>(new Set());
  const [checkingSubmissions, setCheckingSubmissions] = useState(false);
  const [submissionCheckedAt, setSubmissionCheckedAt] = useState<string | null>(null);
  const [submissionProgress, setSubmissionProgress] = useState(0);
  const progressRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Novedades (students with administrative novelties like pending cancellation)
  const [novedadIds, setNovedadIds] = useState<Set<number>>(new Set());

  // Excluded columns (evidences) - persisted per ficha
  const [excludedEvIds, setExcludedEvIds] = useState<Set<number>>(() => {
    try {
      const saved = localStorage.getItem(`heatmap-excluded-evs-${ficha}`);
      if (saved) return new Set(JSON.parse(saved) as number[]);
    } catch { /* ignore */ }
    return new Set();
  });

  // Excluded rows (students) - persisted per ficha
  const [excludedStudentIds, setExcludedStudentIds] = useState<Set<number>>(() => {
    try {
      const saved = localStorage.getItem(`heatmap-excluded-students-${ficha}`);
      if (saved) return new Set(JSON.parse(saved) as number[]);
    } catch { /* ignore */ }
    return new Set();
  });

  // Auto-load cached submission status + novedades on mount
  useEffect(() => {
    if (!ficha) return;
    checkSubmissionStatus(ficha, [], false).then((res) => {
      if (res.pending_cells.length > 0) {
        setPendingCells(new Set(res.pending_cells));
        setSubmissionCheckedAt(res.checked_at);
      }
    }).catch(() => { /* no cache yet, ignore */ });
    fetchNovedades(ficha).then((res) => {
      if (res.total > 0) {
        const ids = new Set(res.records.map((r) => r.user_id));
        setNovedadIds(ids);
        // Auto-exclude novedad students from PDF
        setExcludedStudentIds((prev) => {
          const next = new Set(prev);
          for (const id of ids) next.add(id);
          return next;
        });
      }
    }).catch(() => { /* ignore */ });
  }, [ficha]);

  // Persist excluded evidences
  useEffect(() => {
    const key = `heatmap-excluded-evs-${ficha}`;
    if (excludedEvIds.size === 0) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(Array.from(excludedEvIds)));
  }, [excludedEvIds, ficha]);

  // Persist excluded students
  useEffect(() => {
    const key = `heatmap-excluded-students-${ficha}`;
    if (excludedStudentIds.size === 0) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(Array.from(excludedStudentIds)));
  }, [excludedStudentIds, ficha]);

  const toggleEvidence = useCallback((id: number) => {
    setExcludedEvIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleStudent = useCallback((id: number) => {
    setExcludedStudentIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Filter evidences by etapa
  const filteredEvidences = useMemo(() => {
    if (evidenceFilter === "all") return evidences;
    if (evidenceFilter === "lectiva") return evidences.filter((e) => isLectiva(e.name));
    return evidences.filter((e) => !isLectiva(e.name));
  }, [evidences, evidenceFilter]);

  const filteredEvidenceIds = useMemo(
    () => filteredEvidences.map((e) => e.item_id),
    [filteredEvidences]
  );

  // Evidences selected for PDF (excluded ones filtered out)
  const pdfEvidences = useMemo(
    () => filteredEvidences.filter((e) => !excludedEvIds.has(e.item_id)),
    [filteredEvidences, excludedEvIds]
  );

  const handleCheckSubmissions = useCallback(async () => {
    if (!ficha || checkingSubmissions) return;
    setCheckingSubmissions(true);
    setSubmissionProgress(0);

    // Simulate progress (~2.5s per evidence)
    const totalEvs = pdfEvidences.length;
    let current = 0;
    progressRef.current = setInterval(() => {
      current++;
      if (current <= totalEvs) setSubmissionProgress(current);
    }, 2500);

    try {
      const itemIds = pdfEvidences.map((e) => e.item_id);
      const res = await checkSubmissionStatus(ficha, itemIds, true);
      setPendingCells(new Set(res.pending_cells));
      setSubmissionCheckedAt(res.checked_at);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("404")) {
        alert("Primero debes sincronizar los assignments desde la pantalla 'Por Calificar' de esta ficha.");
      } else {
        console.error("Failed to check submissions:", err);
      }
    } finally {
      if (progressRef.current) clearInterval(progressRef.current);
      setCheckingSubmissions(false);
      setSubmissionProgress(0);
    }
  }, [ficha, pdfEvidences, checkingSubmissions]);

  const filteredAndSorted = useMemo(() => {
    // countGrades es O(evidencias); precomputarlo una vez por aprendiz
    // evita recalcularlo en el filtro y ~2·log(n) veces por comparación
    // del sort (~98.000 operaciones → ~8.900).
    const counts = new Map(
      students.map((s) => [s.user_id, countGrades(s, filteredEvidenceIds)])
    );
    const of = (s: StudentItem) => counts.get(s.user_id)!;

    let result = students.filter((s) => {
      if (studentFilter === "all") return true;
      const { aprobadas, pendientes, desaprobadas } = of(s);
      const total = filteredEvidenceIds.length;
      switch (studentFilter) {
        case "matricula_activa":
          return s.status === "Activo";
        case "matricula_cancelada":
          return s.status === "Suspendido";
        case "con_actividad":
          return aprobadas + desaprobadas > 0;
        case "sin_actividad":
          return aprobadas + desaprobadas === 0;
        case "con_pendientes":
          return pendientes > 0;
        case "todo_aprobado":
          return aprobadas === total;
        case "con_desaprobadas":
          return desaprobadas > 0;
        case "sin_novedad":
          return !novedadIds.has(s.user_id);
        case "con_novedad":
          return novedadIds.has(s.user_id);
        default:
          return true;
      }
    });

    result = [...result].sort((a, b) => {
      switch (sortKey) {
        case "name_asc":
          return a.full_name.localeCompare(b.full_name);
        case "name_desc":
          return b.full_name.localeCompare(a.full_name);
        case "mas_aprobadas":
          return of(b).aprobadas - of(a).aprobadas;
        case "mas_pendientes":
          return of(b).pendientes - of(a).pendientes;
        case "mas_desaprobadas":
          return of(b).desaprobadas - of(a).desaprobadas;
        default:
          return 0;
      }
    });

    return result;
  }, [students, filteredEvidenceIds, sortKey, studentFilter, novedadIds]);

  const handleExportPDF = useCallback(() => {
    const html = buildHeatmapPdfHtml({
      ficha,
      courseName,
      evidenceFilter,
      totalStudents: students.length,
      students: filteredAndSorted.filter((s) => !excludedStudentIds.has(s.user_id)),
      evidences: pdfEvidences,
      pendingCells,
      includeDetail: includeDetailInPDF,
    });

    const printWindow = window.open("", "_blank");
    if (!printWindow) return;

    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.onload = () => {
      printWindow.print();
    };
  }, [filteredAndSorted, pdfEvidences, students, ficha, courseName, evidenceFilter, includeDetailInPDF, excludedStudentIds, pendingCells]);

  const gridWidth = filteredEvidenceIds.length * (CELL_SIZE + GAP);

  // Delegación del hover: un solo handler en el contenedor lee data-si/-ei
  // de la celda bajo el cursor y actualiza el tooltip imperativamente.
  const handleCellHover = (e: React.MouseEvent) => {
    const tip = tooltipRef.current;
    if (!tip) return;
    const cell = (e.target as HTMLElement).closest<HTMLElement>("[data-si]");
    if (!cell) {
      tip.style.display = "none";
      return;
    }
    const student = filteredAndSorted[Number(cell.dataset.si)];
    const ev = filteredEvidences[Number(cell.dataset.ei)];
    if (!student || !ev) {
      tip.style.display = "none";
      return;
    }
    const value = student.grades[String(ev.item_id)]?.value ?? "-";
    const suspended = student.status === "Suspendido" ? " (Suspendido)" : "";
    tip.textContent = `${student.full_name}${suspended}\n${ev.name}\nValor: ${value}`;
    tip.style.left = `${e.clientX + 12}px`;
    tip.style.top = `${e.clientY - 10}px`;
    tip.style.display = "block";
  };

  const hideTooltip = () => {
    if (tooltipRef.current) tooltipRef.current.style.display = "none";
  };

  // Count evidences by etapa
  const lectivaCount = useMemo(() => evidences.filter((e) => isLectiva(e.name)).length, [evidences]);
  const productivaCount = evidences.length - lectivaCount;

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <div aria-hidden="true" className="h-3 w-3 rounded-[2px] bg-ok" />{" "}
          Aprobado (A)
        </div>
        <div className="flex items-center gap-1.5">
          <div aria-hidden="true" className="h-3 w-3 rounded-[2px] bg-danger" />{" "}
          Desaprobado (D)
        </div>
        <div className="flex items-center gap-1.5">
          <div aria-hidden="true" className="h-3 w-3 rounded-[2px] bg-pending" />{" "}
          Pendiente (-)
        </div>
        {pendingCells.size > 0 && (
          <div className="flex items-center gap-1.5">
            <div aria-hidden="true" className="h-3 w-3 rounded-[2px] bg-warn" />{" "}
            Enviado sin calificar
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">Ordenar:</label>
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="h-7 rounded-md border bg-background px-2 text-xs text-foreground transition-[border-color,box-shadow] duration-150 ease-out focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="name_asc">Nombre A-Z</option>
            <option value="name_desc">Nombre Z-A</option>
            <option value="mas_aprobadas">Mas aprobadas</option>
            <option value="mas_pendientes">Mas pendientes</option>
            <option value="mas_desaprobadas">Mas desaprobadas</option>
          </select>
        </div>
        <div className="flex items-center gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">Aprendices:</label>
          <select
            value={studentFilter}
            onChange={(e) => setStudentFilter(e.target.value as StudentFilterKey)}
            className="h-7 rounded-md border bg-background px-2 text-xs text-foreground transition-[border-color,box-shadow] duration-150 ease-out focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="all">Todos</option>
            <option value="matricula_activa">Matricula activa</option>
            <option value="matricula_cancelada">Matricula cancelada</option>
            <option value="con_actividad">Con actividad</option>
            <option value="sin_actividad">Sin actividad</option>
            <option value="con_pendientes">Con pendientes</option>
            <option value="todo_aprobado">Todo aprobado</option>
            <option value="con_desaprobadas">Con desaprobadas</option>
            {novedadIds.size > 0 && (
              <>
                <option value="sin_novedad">Sin novedad ({students.filter(s => !novedadIds.has(s.user_id)).length})</option>
                <option value="con_novedad">Con novedad ({novedadIds.size})</option>
              </>
            )}
          </select>
        </div>
        <div className="flex items-center gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">Evidencias:</label>
          <select
            value={evidenceFilter}
            onChange={(e) => setEvidenceFilter(e.target.value as EvidenceFilterKey)}
            className="h-7 rounded-md border bg-background px-2 text-xs text-foreground transition-[border-color,box-shadow] duration-150 ease-out focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="all">Todas ({evidences.length})</option>
            <option value="lectiva">Etapa Lectiva ({lectivaCount})</option>
            <option value="productiva">Etapa Productiva ({productivaCount})</option>
          </select>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {novedadIds.size > 0 && (
            <span className="text-xs text-caution-fg font-medium">
              {novedadIds.size} con novedad
            </span>
          )}
          <button
            onClick={handleCheckSubmissions}
            disabled={checkingSubmissions}
            className="cursor-pointer rounded-md border border-warn-border bg-warn-soft px-3 py-1.5 text-xs font-medium tabular-nums text-warn-fg transition-colors duration-150 ease-out hover:bg-warn-border/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:opacity-50"
            title={submissionCheckedAt ? `Última verificación: ${new Date(submissionCheckedAt).toLocaleString("es-CO")}` : "Consulta entregas pendientes de calificar desde Zajuna"}
          >
            {checkingSubmissions
              ? `Verificando ${submissionProgress}/${pdfEvidences.length} evidencias...`
              : pendingCells.size > 0
                ? `Entregas (${pendingCells.size}) ↻`
                : "Verificar entregas"}
          </button>
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <Button variant="outline" size="sm" pill>
                <FileDown aria-hidden="true" />
                Exportar PDF
                <ChevronDown aria-hidden="true" />
              </Button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={6}
                className="z-50 min-w-[16rem] rounded-lg border bg-popover p-1 text-sm text-popover-foreground shadow-lg"
              >
                {(
                  [
                    [includeDetailInPDF, setIncludeDetailInPDF, "Incluir listado de pendientes"],
                    [pickForPdf, setPickForPdf, "Elegir en el mapa qué va al PDF"],
                  ] as const
                ).map(([checked, set, label]) => (
                  <DropdownMenu.CheckboxItem
                    key={label}
                    checked={checked}
                    onCheckedChange={(v) => set(v === true)}
                    onSelect={(e) => e.preventDefault()}
                    className="flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1.5 outline-none data-[highlighted]:bg-accent"
                  >
                    <span className="flex h-4 w-4 items-center justify-center rounded border border-input">
                      <DropdownMenu.ItemIndicator>
                        <Check aria-hidden="true" className="h-3 w-3" />
                      </DropdownMenu.ItemIndicator>
                    </span>
                    {label}
                  </DropdownMenu.CheckboxItem>
                ))}
                {(excludedStudentIds.size > 0 || excludedEvIds.size > 0) && (
                  <>
                    <DropdownMenu.Separator className="my-1 h-px bg-border" />
                    <p className="px-2 py-1 text-xs tabular-nums text-muted-foreground">
                      Van {filteredAndSorted.length - excludedStudentIds.size} de {filteredAndSorted.length}{" "}
                      aprendices y {filteredEvidences.length - excludedEvIds.size} de {filteredEvidences.length}{" "}
                      evidencias
                    </p>
                    <DropdownMenu.Item
                      onSelect={() => {
                        setExcludedStudentIds(new Set());
                        setExcludedEvIds(new Set());
                      }}
                      className="cursor-pointer select-none rounded-md px-2 py-1.5 text-xs outline-none data-[highlighted]:bg-accent"
                    >
                      Incluir todo de nuevo
                    </DropdownMenu.Item>
                  </>
                )}
                <DropdownMenu.Separator className="my-1 h-px bg-border" />
                <DropdownMenu.Item
                  onSelect={handleExportPDF}
                  className="flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1.5 font-medium outline-none data-[highlighted]:bg-accent"
                >
                  <FileDown aria-hidden="true" className="h-4 w-4" />
                  Descargar PDF
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </div>

      <div
        className="relative overflow-auto rounded-xl border bg-card shadow-card"
        onMouseOver={handleCellHover}
        onMouseLeave={hideTooltip}
      >
        <div className="relative" style={{ minWidth: gridWidth + 220 }}>
          {/* Fila para elegir evidencias del PDF: solo en modo "Elegir en el mapa" */}
          {pickForPdf && (
          <div className="flex items-center" style={{ height: CELL_SIZE + GAP, marginBottom: 2 }}>
            <div className="sticky left-0 z-10 flex flex-shrink-0 items-center gap-1 bg-card pr-2" style={{ width: 210 }}>
              <div className="mr-1 flex items-center gap-0.5">
                <button
                  onClick={() => setExcludedStudentIds(new Set())}
                  className="rounded-sm text-[9px] font-medium text-sena-green-dark hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring dark:text-sena-green"
                  title="Incluir todos en PDF"
                >
                  todos
                </button>
                <span aria-hidden="true" className="text-[9px] text-muted-foreground">|</span>
                <button
                  onClick={() => setExcludedStudentIds(new Set(filteredAndSorted.map((s) => s.user_id)))}
                  className="rounded-sm text-[9px] font-medium text-sena-green-dark hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring dark:text-sena-green"
                  title="Excluir todos del PDF"
                >
                  ning.
                </button>
              </div>
              <span aria-hidden="true" className="mx-0.5 text-[9px] text-muted-foreground">|</span>
              <button
                onClick={() => setExcludedEvIds(new Set())}
                className="rounded-sm text-[9px] font-medium text-sena-green-dark hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring dark:text-sena-green"
                title="Seleccionar todas las evidencias"
              >
                todas
              </button>
              <span aria-hidden="true" className="text-[9px] text-muted-foreground">|</span>
              <button
                onClick={() => setExcludedEvIds(new Set(filteredEvidences.map((e) => e.item_id)))}
                className="rounded-sm text-[9px] font-medium text-sena-green-dark hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring dark:text-sena-green"
                title="Deseleccionar todas las evidencias"
              >
                ninguna
              </button>
            </div>
            <div className="flex gap-px">
              {filteredEvidences.map((ev) => (
                <div
                  key={ev.item_id}
                  style={{ width: CELL_SIZE, height: CELL_SIZE }}
                  className={`flex-shrink-0 rounded-[2px] cursor-pointer border transition-colors ${
                    excludedEvIds.has(ev.item_id)
                      ? "bg-danger-soft border-danger"
                      : "bg-ok-soft border-ok"
                  }`}
                  title={`${extractGACode(ev.name)} — clic para ${excludedEvIds.has(ev.item_id) ? "incluir" : "excluir"}`}
                  onClick={() => toggleEvidence(ev.item_id)}
                />
              ))}
            </div>
          </div>
          )}
          {filteredAndSorted.map((student, si) => {
            const isSuspended = student.status === "Suspendido";
            const isExcluded = excludedStudentIds.has(student.user_id);
            const hasNovedad = novedadIds.has(student.user_id);
            return (
              <div
                key={student.user_id}
                className="flex items-center"
                style={{
                  height: CELL_SIZE + GAP,
                  opacity: isSuspended || hasNovedad ? 0.45 : 1,
                  // El navegador omite layout/paint de las filas fuera del
                  // viewport (virtualización ligera, sin librerías)
                  contentVisibility: "auto",
                  containIntrinsicSize: `auto ${CELL_SIZE + GAP}px`,
                }}
              >
                {/* Student checkbox + name (sticky) */}
                <div
                  className={`sticky left-0 z-10 flex flex-shrink-0 items-center gap-1 bg-card pr-2 text-xs ${isSuspended ? "line-through text-muted-foreground" : ""} ${hasNovedad ? "text-caution-fg" : ""}`}
                  style={{ width: 210 }}
                >
                  {pickForPdf && (
                  <div
                    onClick={() => toggleStudent(student.user_id)}
                    style={{ width: CELL_SIZE - 2, height: CELL_SIZE - 2, minWidth: CELL_SIZE - 2 }}
                    className={`rounded-[2px] cursor-pointer border transition-colors ${
                      hasNovedad
                        ? "bg-caution-soft border-caution"
                        : isExcluded
                          ? "bg-danger-soft border-danger"
                          : "bg-ok-soft border-ok"
                    }`}
                    title={`${student.full_name}${hasNovedad ? " (Novedad: cancelacion en proceso)" : ""} — clic para ${isExcluded ? "incluir" : "excluir"} del PDF`}
                  />
                  )}
                  <span className="truncate" title={`${student.full_name}${isSuspended ? " (Suspendido)" : ""}${hasNovedad ? " (Novedad)" : ""}`}>
                    {student.full_name}
                  </span>
                </div>

                {/* Grade cells */}
                <div className="flex gap-px">
                  {filteredEvidenceIds.map((eid, ei) => {
                    const grade = student.grades[String(eid)];
                    const value = grade?.value ?? "-";
                    const isSubmitted = pendingCells.has(`${eid}:${student.user_id}`);
                    return (
                      <div
                        key={eid}
                        data-si={si}
                        data-ei={ei}
                        style={{
                          width: CELL_SIZE,
                          height: CELL_SIZE,
                          backgroundColor: gradeColor(value, isSubmitted),
                        }}
                        className="flex-shrink-0 rounded-[2px] cursor-pointer"
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Tooltip imperativo (posicionado por handleCellHover, sin re-renders) */}
        <div
          ref={tooltipRef}
          style={{ display: "none" }}
          className="pointer-events-none fixed z-50 whitespace-pre-line rounded-md bg-foreground px-3 py-2 text-xs text-background shadow-lg"
        />
      </div>

      <p className="text-xs tabular-nums text-muted-foreground">
        {filteredAndSorted.length} de {students.length} aprendices x{" "}
        {filteredEvidences.length} de {evidences.length} evidencias
      </p>
    </div>
  );
}
