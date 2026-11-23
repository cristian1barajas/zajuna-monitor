"use client";

import { useRef, useState } from "react";
import { Upload, CheckCircle2, AlertCircle } from "lucide-react";
import type { SofiaReportInput, SofiaStudent, SofiaJudgment } from "@/types/api";

interface SofiaUploaderProps {
  onParsed: (data: SofiaReportInput) => void;
}

export function SofiaUploader({ onParsed }: SofiaUploaderProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ students: number; raps: number } | null>(null);

  const handleFile = (file: File) => {
    setError(null);
    setFileName(file.name);
    setPreview(null);

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const XLSX = await import("xlsx");
        const data = new Uint8Array(e.target?.result as ArrayBuffer);
        const wb = XLSX.read(data, { type: "array" });
        const ws = wb.Sheets[wb.SheetNames[0]];

        // The Sofia report has metadata in rows 1-12, headers in row 13
        // Read all rows starting from the headers
        const allRows = XLSX.utils.sheet_to_json<Record<string, string>>(ws, {
          defval: "",
          range: 12, // 0-indexed: row 13 becomes headers
        });

        if (allRows.length === 0) {
          setError("No se encontraron datos en el reporte Sofia.");
          return;
        }

        // Detect key columns
        // Actual headers: "Tipo de Documento", "Numero de Documento", "Nombre",
        // "Apellidos", "Estado", "Competencia", "Resultado de Aprendizaje",
        // "Juicio de Evaluacion"
        const keys = Object.keys(allRows[0]);

        // "Numero de Documento" (not "Tipo de Documento")
        const docCol = keys.find(
          (k) => k.toLowerCase().includes("numero") && k.toLowerCase().includes("documento"),
        ) ?? keys.find(
          (k) => k.toLowerCase().includes("documento") && !k.toLowerCase().includes("tipo"),
        );
        const nameCol = keys.find(
          (k) => k.toLowerCase() === "nombre" || (k.toLowerCase().includes("nombre") && !k.toLowerCase().includes("programa")),
        );
        const apellidosCol = keys.find(
          (k) => k.toLowerCase().includes("apellido"),
        );
        // "Estado" (may or may not include "aprendiz")
        const statusCol = keys.find(
          (k) => k.toLowerCase().includes("estado"),
        );
        // "Competencia" - single column with "code - description"
        const compCol = keys.find(
          (k) => k.toLowerCase().includes("competencia"),
        );
        // "Resultado de Aprendizaje" - single column with "code - seq description"
        const rapCol = keys.find(
          (k) => k.toLowerCase().includes("resultado") && k.toLowerCase().includes("aprendizaje"),
        ) ?? keys.find(
          (k) => k.toLowerCase().includes("resultado"),
        );
        const juicioCol = keys.find((k) => k.toLowerCase().includes("juicio"));

        if (!docCol || !juicioCol) {
          setError(
            `No se encontraron columnas requeridas. Detectadas: ${keys.slice(0, 10).join(", ")}... Se requieren: documento, juicio.`,
          );
          return;
        }

        // Group by student document, filter EN FORMACION
        const studentMap = new Map<
          string,
          { full_name: string; student_status: string; judgments: SofiaJudgment[] }
        >();
        const rapCodes = new Set<string>();
        const competencyMap: Record<string, string> = {};

        // Try to extract program name from metadata rows
        // Row 6 col3 has "Denominacion" value like "ANALISIS Y DESARROLLO DE SOFTWARE"
        let programName = "";
        const rawMeta = XLSX.utils.sheet_to_json<string[]>(ws, {
          defval: "",
          header: 1,
          range: "A1:D12",
        });
        for (const row of rawMeta) {
          const label = String(row[0] ?? "").toLowerCase();
          const value = String(row[2] ?? row[1] ?? "").trim();
          if (label.includes("denominacion") || label.includes("programa")) {
            if (value) programName = value;
          }
        }

        for (const row of allRows) {
          const doc = row[docCol]?.toString().trim();
          const status = statusCol ? row[statusCol]?.trim() : "EN FORMACION";

          if (!doc || /^\D+$/.test(doc)) continue; // skip non-numeric docs like "CC"
          if (status && !status.toUpperCase().includes("EN FORMACION")) continue;

          // Build full name from Nombre + Apellidos
          const nombre = nameCol ? row[nameCol]?.trim() : "";
          const apellidos = apellidosCol ? row[apellidosCol]?.trim() : "";
          const fullName = apellidos ? `${nombre} ${apellidos}` : nombre;

          if (!studentMap.has(doc)) {
            studentMap.set(doc, {
              full_name: fullName,
              student_status: status || "EN FORMACION",
              judgments: [],
            });
          }

          // Parse "Competencia" column: "38392 - Establecer requisitos..."
          const compRaw = compCol ? row[compCol]?.toString().trim() : "";
          let compCode = "";
          let compDesc = "";
          const compParts = compRaw.match(/^(\d+)\s*-\s*(.+)$/);
          if (compParts) {
            compCode = compParts[1];
            compDesc = compParts[2].trim();
          } else {
            compDesc = compRaw;
          }

          // Parse "Resultado de Aprendizaje" column: "593344 - 02  RECOLECTAR..."
          const rapRaw = rapCol ? row[rapCol]?.toString().trim() : "";
          let rapCode = "";
          let rapDesc = "";
          const rapParts = rapRaw.match(/^(\d+)\s*-\s*(.+)$/);
          if (rapParts) {
            rapCode = rapParts[1];
            rapDesc = rapParts[2].trim();
          } else {
            rapDesc = rapRaw;
          }

          const juicio = row[juicioCol]?.trim() || "POR EVALUAR";

          if (rapCode) rapCodes.add(rapCode);

          // Build competency map: Sofia key → itself (for bridge matching)
          if (compCode && compDesc) {
            const sofiaKey = `${compCode} - ${compDesc}`;
            if (!competencyMap[sofiaKey]) {
              competencyMap[sofiaKey] = sofiaKey;
            }
          }

          studentMap.get(doc)!.judgments.push({
            competencia_code: compCode,
            competencia_desc: compDesc,
            rap_code: rapCode,
            rap_desc: rapDesc,
            juicio,
          });
        }

        const students: SofiaStudent[] = [];
        for (const [doc, info] of studentMap) {
          students.push({
            document: doc,
            full_name: info.full_name,
            student_status: info.student_status,
            judgments: info.judgments,
          });
        }

        const result: SofiaReportInput = {
          program_name: programName || "PROGRAMA NO DETECTADO",
          total_students: students.length,
          total_raps: rapCodes.size,
          students,
          competency_map: competencyMap,
        };

        setPreview({ students: students.length, raps: rapCodes.size });
        onParsed(result);
      } catch (err) {
        setError(`Error al leer Excel: ${err instanceof Error ? err.message : String(err)}`);
      }
    };
    reader.readAsArrayBuffer(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-label="Seleccionar archivo Excel del reporte de juicios de Sofia Plus"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileRef.current?.click();
          }
        }}
        className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-input p-8 text-center transition-colors duration-150 ease-out hover:border-sena-green hover:bg-sena-green-tint/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Upload aria-hidden="true" className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">
          Reporte de Juicios Evaluativos Sofia Plus (Excel)
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Ej: Reporte de Juicios Evaluativos.xlsx — Metadata filas 1-12, datos desde fila 13
        </p>
        {fileName && (
          <p className="text-xs font-medium text-sena-green-dark dark:text-sena-green">
            {fileName}
          </p>
        )}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".xlsx,.xls"
        onChange={handleChange}
        className="hidden"
      />

      {preview && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-md border border-ok-border bg-ok-soft px-3 py-2.5 text-sm font-medium tabular-nums text-ok-fg"
        >
          <CheckCircle2 aria-hidden="true" className="h-4 w-4 shrink-0" />
          {preview.students} aprendices EN FORMACION, {preview.raps} RAPs detectados
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-md border border-danger-border bg-danger-soft px-3 py-2.5 text-sm font-medium leading-snug text-danger-fg"
        >
          <AlertCircle aria-hidden="true" className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}
