"use client";

import { useRef, useState } from "react";
import { FileUp, Loader2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { previewCronogramaPdfs } from "@/lib/api";
import type { CronogramaPdfPreview } from "@/types/api";

interface CronogramaUploaderProps {
  ficha: string;
  /** CSV: reemplaza el cronograma completo. */
  onParsed: (entries: { evidence_name: string; cutoff_date: string }[]) => void;
  /** PDF (uno o varios meses): se suman al cronograma actual. */
  onPdfPreview: (preview: CronogramaPdfPreview) => void;
  /** "button" deja solo el botón Subir archivos; los errores salen por onError. */
  variant?: "dropzone" | "button";
  onError?: (message: string | null) => void;
}

const isPdf = (file: File) =>
  file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

export function CronogramaUploader({
  ficha,
  onParsed,
  onPdfPreview,
  variant = "dropzone",
  onError,
}: CronogramaUploaderProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [fileLabel, setFileLabel] = useState<string | null>(null);
  const [reading, setReading] = useState(false);

  const setError = (message: string | null) => {
    if (onError) onError(message);
    else setLocalError(message);
  };
  const error = onError ? null : localError;

  const handlePdfs = async (files: File[]) => {
    setReading(true);
    try {
      onPdfPreview(await previewCronogramaPdfs(ficha, files));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron leer los PDF.");
    } finally {
      setReading(false);
    }
  };

  const handleCsv = async (file: File) => {
    const Papa = (await import("papaparse")).default;
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete(results) {
        const rows = results.data as Record<string, string>[];
        if (rows.length === 0) {
          setError("El archivo CSV está vacío.");
          return;
        }

        // Try to detect column names (flexible)
        const first = rows[0];
        const keys = Object.keys(first);

        const nameCol = keys.find(
          (k) =>
            k.toLowerCase().includes("evidencia") ||
            k.toLowerCase().includes("evidence") ||
            k.toLowerCase().includes("nombre"),
        );
        const dateCol = keys.find(
          (k) =>
            k.toLowerCase().includes("fecha") ||
            k.toLowerCase().includes("date") ||
            k.toLowerCase().includes("corte"),
        );

        if (!nameCol || !dateCol) {
          setError(
            `No se encontraron las columnas requeridas. Columnas detectadas: ${keys.join(", ")}. Se esperan columnas con "evidencia" y "fecha".`,
          );
          return;
        }

        const entries = rows
          .filter((r) => r[nameCol]?.trim() && r[dateCol]?.trim())
          .map((r) => ({
            evidence_name: r[nameCol].trim(),
            cutoff_date: normalizeDateStr(r[dateCol].trim()),
          }));

        if (entries.length === 0) {
          setError("No se encontraron filas válidas con evidencia y fecha.");
          return;
        }

        onParsed(entries);
      },
      error(err) {
        setError(`Error al leer CSV: ${err.message}`);
      },
    });
  };

  const handleFiles = (files: File[]) => {
    if (files.length === 0) return;
    setError(null);
    const pdfs = files.filter(isPdf);

    if (pdfs.length > 0 && pdfs.length < files.length) {
      setError("Sube solo PDF o solo un CSV, sin mezclarlos.");
      return;
    }
    if (pdfs.length > 0) {
      setFileLabel(pdfs.length === 1 ? pdfs[0].name : `${pdfs.length} PDF`);
      void handlePdfs(pdfs);
      return;
    }
    if (files.length > 1) {
      setError("Sube un solo CSV a la vez.");
      return;
    }
    setFileLabel(files[0].name);
    void handleCsv(files[0]);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(Array.from(e.target.files ?? []));
    // Permite volver a elegir los mismos archivos.
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFiles(Array.from(e.dataTransfer.files ?? []));
  };

  const input = (
    <input
      ref={fileRef}
      type="file"
      accept=".pdf,.csv,.txt"
      multiple
      onChange={handleChange}
      className="hidden"
    />
  );

  if (variant === "button") {
    return (
      <>
        <Button
          variant="outline"
          size="sm"
          pill
          onClick={() => fileRef.current?.click()}
          disabled={reading}
          title="PDF: se suman al cronograma. CSV: lo reemplaza."
        >
          {reading ? <Loader2 aria-hidden="true" className="animate-spin" /> : <FileUp aria-hidden="true" />}
          {reading ? "Leyendo PDF…" : "Subir archivos"}
        </Button>
        {input}
      </>
    );
  }

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-busy={reading}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => !reading && fileRef.current?.click()}
        onKeyDown={(e) => {
          if (!reading && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            fileRef.current?.click();
          }
        }}
        className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed p-8 text-center transition-colors duration-150 ease-out hover:border-sena-green hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {reading ? (
          <Loader2 aria-hidden="true" className="h-6 w-6 animate-spin text-muted-foreground" />
        ) : (
          <Upload aria-hidden="true" className="h-6 w-6 text-muted-foreground" />
        )}
        <p className="text-sm font-medium text-foreground">
          {reading
            ? "Leyendo los PDF…"
            : "Arrastra los PDF del cronograma aquí o haz clic para elegirlos"}
        </p>
        <p className="text-xs text-muted-foreground">
          Puedes subir varios meses a la vez. También acepta un CSV con columnas{" "}
          <span className="font-mono">evidencia,fecha</span>.
        </p>
        {fileLabel && (
          <p className="text-xs font-medium text-sena-green-dark dark:text-sena-green">
            {fileLabel}
          </p>
        )}
      </div>

      {input}

      {error && (
        <div className="rounded-md border border-danger-border bg-danger-soft p-3 text-sm text-danger-fg">
          {error}
        </div>
      )}
    </div>
  );
}

/**
 * Normalize common date formats to YYYY-MM-DD.
 * Handles: "15/02/2026", "15-02-2026", "2026-02-15", "2026/02/15"
 */
function normalizeDateStr(s: string): string {
  // Already YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

  // DD/MM/YYYY or DD-MM-YYYY
  const dmy = s.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);
  if (dmy) {
    return `${dmy[3]}-${dmy[2].padStart(2, "0")}-${dmy[1].padStart(2, "0")}`;
  }

  // YYYY/MM/DD
  const ymd = s.match(/^(\d{4})\/(\d{2})\/(\d{2})$/);
  if (ymd) {
    return `${ymd[1]}-${ymd[2]}-${ymd[3]}`;
  }

  return s;
}
