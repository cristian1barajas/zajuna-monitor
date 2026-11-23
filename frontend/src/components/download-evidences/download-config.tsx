"use client";

import { FolderOpen } from "lucide-react";
import { MultiSelect } from "@/components/pending-grading/evidence-filters";

interface DownloadConfigProps {
  targetDir: string;
  onTargetDirChange: (dir: string) => void;
  ficha: string;
  includeInstrument: boolean;
  onIncludeInstrumentChange: (v: boolean) => void;
  instrumentAvailable: boolean;
  statuses: string[];
  selectedStatuses: Set<string>;
  onStatusesChange: (next: Set<string>) => void;
}

/** Barra de herramientas sobre la tabla de envíos: estado, instrumento y ruta. */
export function DownloadConfig({
  targetDir,
  onTargetDirChange,
  ficha,
  includeInstrument,
  onIncludeInstrumentChange,
  instrumentAvailable,
  statuses,
  selectedStatuses,
  onStatusesChange,
}: DownloadConfigProps) {
  return (
    <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
      {statuses.length > 0 && (
        <MultiSelect
          label="Estado"
          options={statuses}
          selected={selectedStatuses}
          onChange={onStatusesChange}
        />
      )}

      {instrumentAvailable && (
        <label className="flex h-9 items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeInstrument}
            onChange={(e) => onIncludeInstrumentChange(e.target.checked)}
            className="h-4 w-4 rounded border-input"
          />
          Incluir instrumento de evaluación
        </label>
      )}

      <div className="min-w-[16rem] flex-1">
        <div className="relative">
          <FolderOpen
            aria-hidden="true"
            className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <input
            id="ruta-descarga"
            type="text"
            value={targetDir}
            onChange={(e) => onTargetDirChange(e.target.value)}
            aria-label="Ruta de descarga"
            className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 font-mono text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground/70 focus:border-sena-green focus:ring-2 focus:ring-ring/30"
            placeholder="C:\Users\...\Downloads\Zajuna"
          />
        </div>
        <p className="mt-1 truncate text-xs text-muted-foreground">
          Se guarda en{" "}
          <span className="font-mono font-medium text-foreground">
            {targetDir}\{ficha}\
          </span>
        </p>
      </div>
    </div>
  );
}
