"use client";

import { useState } from "react";
import { ClipboardCopy, GraduationCap } from "lucide-react";

/** Mensaje listo para pegar en Claude Code y calificar la carpeta descargada. */
export function GradingPrompt({ folderPath }: { folderPath: string }) {
  const [copied, setCopied] = useState(false);
  const prompt = `Califica las evidencias de la siguiente carpeta, pero debes leer una por una, lees una y generas la calificación en el archivo HTML respectivo, y luego lees la siguiente, y generas el siguiente archivo HTML: ${folderPath}`;

  return (
    <div className="space-y-3 rounded-lg border border-notice-border bg-notice-soft p-4">
      <div className="flex items-center gap-2">
        <GraduationCap aria-hidden="true" className="h-5 w-5 text-notice-fg" />
        <p className="text-sm font-semibold text-notice-fg">Calificar evidencias</p>
      </div>
      <p className="text-xs leading-relaxed text-notice-fg">
        Copia el siguiente mensaje y pégalo en Claude Code para calificar automáticamente todas
        las evidencias descargadas:
      </p>
      <div className="flex items-center gap-2">
        <code className="flex-1 truncate rounded bg-notice-border/40 px-2 py-1.5 text-xs text-notice-fg">
          {prompt}
        </code>
        <button
          onClick={() => {
            navigator.clipboard.writeText(prompt);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }}
          className="flex shrink-0 items-center gap-1 rounded-md border border-notice-border bg-notice-border/40 px-2.5 py-1.5 text-xs font-medium text-notice-fg transition-colors duration-150 ease-out hover:bg-notice-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ClipboardCopy aria-hidden="true" className="h-3.5 w-3.5" />
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
    </div>
  );
}
