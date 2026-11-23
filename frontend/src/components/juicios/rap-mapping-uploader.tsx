"use client";

import { useRef, useState } from "react";
import { Upload, CheckCircle2, AlertCircle } from "lucide-react";
import type { RapMappingInput, RapMappingEntry, RapEvidenciaInput } from "@/types/api";

interface RapMappingUploaderProps {
  onParsed: (data: RapMappingInput) => void;
}

/**
 * Evidence code regex: extracts SENA code like "GA1-220501092-AA1-EV01".
 * Tolerates stray spaces inside the code (real gradebooks contain typos
 * like "GA1- 220501092-AA3-EV03").
 */
const CODE_RE = /GA\s*\d+\s*-\s*\d{6,9}\s*-\s*AA\s*\d+\s*-\s*EV\s*\d+/;

/** Sofia RAP reference: "593346 - 01" (6-digit code + sequence). */
const SOFIA_RAP_RE = /(\d{6})\s*-\s*(\d{2})/g;

/** Zajuna RAP reference: "220501092-01" (9-digit competency + sequence). */
const ZAJUNA_RAP_RE = /(\d{9})\s*-\s*(\d{2})/g;

/** Collapse newlines/extra spaces from Excel cells. */
const norm = (s: string | undefined) => (s ?? "").replace(/\s+/g, " ").trim();

export function RapMappingUploader({ onParsed }: RapMappingUploaderProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ raps: number; evidencias: number } | null>(null);

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
        const rows = XLSX.utils.sheet_to_json<Record<string, string>>(ws, { defval: "" });

        if (rows.length === 0) {
          setError("El archivo Excel esta vacio.");
          return;
        }

        // Detect columns. The reference file has both RAP columns:
        // "RAP ZAJUNA" and "RAP SOFIA PLUS" — the Sofia code (6 digits)
        // is the exact key for the judgments cross-reference.
        const keys = Object.keys(rows[0]);
        const low = (k: string) => k.toLowerCase();
        const faseCol = keys.find((k) => low(k).includes("fase"));
        const compCol = keys.find((k) => low(k).includes("competencia"));
        const rapSofiaCol = keys.find((k) => low(k).includes("rap") && low(k).includes("sofia"));
        const rapZajunaCol =
          keys.find((k) => low(k).includes("rap") && low(k).includes("zajuna")) ??
          keys.find((k) => low(k).includes("rap") && k !== rapSofiaCol);
        const evDescCol = keys.find(
          (k) => low(k).includes("evidencia") && low(k).includes("descripci"),
        );
        const evCodeCol =
          keys.find(
            (k) => low(k).includes("evidencia") && low(k).includes("codigo") && !low(k).includes("descripci"),
          ) ??
          keys.find(
            (k) => (low(k).includes("evidencia") || low(k).includes("nombre")) && k !== evDescCol,
          );

        if (!compCol || !rapZajunaCol || !evCodeCol) {
          setError(
            `No se encontraron columnas requeridas. Detectadas: ${keys.join(", ")}. Se requieren: competencia, rap, evidencia.`,
          );
          return;
        }

        // One mapping entry per RAP. Keyed by Sofia code when available
        // (a cell can reference several RAPs: each gets its own entry and
        // shares the evidence), otherwise by the Zajuna RAP cell (legacy).
        const rapMap = new Map<
          string,
          { fase: string; competencia: string; rap: string; rap_sofia_code: string; evidencias: RapEvidenciaInput[] }
        >();
        let totalEv = 0;

        for (const row of rows) {
          const zajunaCell = norm(row[rapZajunaCol]);
          const comp = norm(row[compCol]);
          const fase = faseCol ? norm(row[faseCol]) : "";
          const evCellRaw = norm(row[evCodeCol]);
          const evDesc = evDescCol ? norm(row[evDescCol]) : "";

          if (!zajunaCell || !evCellRaw) continue;

          const codeMatch = evCellRaw.match(CODE_RE) ?? evDesc.match(CODE_RE);
          const code = codeMatch ? codeMatch[0].replace(/\s+/g, "") : evCellRaw.substring(0, 30);
          const evidencia: RapEvidenciaInput = {
            code,
            item_id: null,
            name: evDesc || evCellRaw,
            matched: false,
          };
          totalEv += 1;

          // Zajuna RAP segments in the cell, indexed by sequence number
          const zajunaBySeq = new Map<string, string>();
          const zajunaRefs = [...zajunaCell.matchAll(ZAJUNA_RAP_RE)];
          for (let i = 0; i < zajunaRefs.length; i++) {
            const start = zajunaRefs[i].index ?? 0;
            const end = i + 1 < zajunaRefs.length ? zajunaRefs[i + 1].index : zajunaCell.length;
            zajunaBySeq.set(zajunaRefs[i][2], zajunaCell.substring(start, end).trim());
          }

          const sofiaCell = rapSofiaCol ? norm(row[rapSofiaCol]) : "";
          const sofiaRefs = [...sofiaCell.matchAll(SOFIA_RAP_RE)];

          // (key, sofia_code, zajuna label) per RAP referenced by the row
          const targets: { key: string; sofiaCode: string; rap: string }[] =
            sofiaRefs.length > 0
              ? sofiaRefs.map((m) => ({
                  key: m[1],
                  sofiaCode: m[1],
                  rap: zajunaBySeq.get(m[2]) ?? zajunaCell,
                }))
              : [{ key: zajunaCell, sofiaCode: "", rap: zajunaCell }];

          for (const t of targets) {
            let entry = rapMap.get(t.key);
            if (!entry) {
              entry = { fase, competencia: comp, rap: t.rap, rap_sofia_code: t.sofiaCode, evidencias: [] };
              rapMap.set(t.key, entry);
            }
            entry.evidencias.push(evidencia);
          }
        }

        const mappings: RapMappingEntry[] = [...rapMap.values()];

        // Try to extract program name from filename or first row
        const programName = file.name.replace(/\.(xlsx|xls|csv)$/i, "")
          .replace(/^Evidencias_RAP_/i, "")
          .replace(/_/g, " ");

        const result: RapMappingInput = {
          program_name: programName,
          mappings,
          stats: {
            total_raps: mappings.length,
            total_evidencias: totalEv,
            matched_evidencias: 0,
            unmatched_evidencias: totalEv,
          },
        };

        setPreview({ raps: mappings.length, evidencias: totalEv });
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
        aria-label="Seleccionar archivo Excel del mapeo Evidencias a RAP"
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
          Mapeo Evidencias → RAP (Excel)
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Ej: Evidencias_RAP_ADSO.xlsx — Columnas: competencia, rap, evidencia
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
          {preview.raps} RAPs, {preview.evidencias} evidencias detectadas
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
