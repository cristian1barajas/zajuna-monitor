"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { RapPorAsignar } from "@/types/api";

export type AsignarModo = "aprobar" | "no_aprobar";

/** Código que se copia con un clic, para pegarlo en el buscador de Sofía Plus. */
function CopyCode({ code, label }: { code: string; label: string }) {
  const [copied, setCopied] = useState(false);
  if (!code) return null;
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(code).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1200);
        });
      }}
      title={`Copiar ${label} ${code}`}
      aria-label={`Copiar ${label} ${code}`}
      className="inline-flex shrink-0 items-center gap-1 rounded-md border bg-muted/40 px-1.5 py-0.5 font-mono text-xs font-semibold tabular-nums text-foreground transition-colors duration-150 ease-out hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {code}
      {copied ? (
        <Check aria-hidden="true" className="h-3 w-3 text-ok-fg" />
      ) : (
        <Copy aria-hidden="true" className="h-3 w-3 text-muted-foreground" />
      )}
    </button>
  );
}

interface RapAsignarCardProps {
  rap: RapPorAsignar;
  modo: AsignarModo;
  checked: Set<string>;
  onToggle: (document: string) => void;
  onToggleAll: (documents: string[], value: boolean) => void;
}

/** Un RAP con sus aprendices (orden alfabético) y una casilla por aprendiz. */
export function RapAsignarCard({ rap, modo, checked, onToggle, onToggleAll }: RapAsignarCardProps) {
  const docs = rap.aprendices.map((a) => a.document);
  const marked = docs.filter((d) => checked.has(d)).length;
  const all = marked === docs.length;

  return (
    <article className="overflow-hidden rounded-lg border bg-card">
      <header className="flex flex-wrap items-start gap-x-3 gap-y-2 border-b bg-muted/30 px-4 py-2.5">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <span className="font-semibold uppercase tracking-wide">RAP</span>
            <CopyCode code={rap.rap_code} label="código del RAP" />
            {rap.rap_programa && <span className="tabular-nums">· {rap.rap_programa}</span>}
            {rap.fase && <span>· {rap.fase}</span>}
          </p>
          <p className="mt-1 text-sm font-medium leading-snug text-foreground">{rap.rap_desc}</p>
        </div>
        <label className="flex shrink-0 cursor-pointer items-center gap-2 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground">
          <Checkbox
            checked={all ? true : marked > 0 ? "indeterminate" : false}
            onCheckedChange={(v) => onToggleAll(docs, v === true)}
            aria-label={`Marcar todos los aprendices del RAP ${rap.rap_code}`}
          />
          <span className="tabular-nums">
            {marked} de {docs.length}
          </span>
        </label>
      </header>
      <ul className="divide-y">
        {rap.aprendices.map((a, i) => {
          const on = checked.has(a.document);
          return (
            <li key={a.document}>
              <label
                className={cn(
                  "flex cursor-pointer items-center gap-3 px-4 py-2 text-sm transition-colors duration-150 ease-out hover:bg-accent/40",
                  on && "bg-accent/30",
                )}
              >
                <Checkbox checked={on} onCheckedChange={() => onToggle(a.document)} />
                <span className="w-6 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                  {i + 1}
                </span>
                <span className="min-w-0 flex-1 truncate font-medium">{a.full_name}</span>
                <span className="hidden shrink-0 font-mono text-xs tabular-nums text-muted-foreground sm:inline">
                  {a.document}
                </span>
                {modo === "aprobar" ? (
                  <span className="shrink-0 rounded-full bg-ok-soft px-2 py-0.5 text-[11px] font-medium text-ok-fg">
                    {a.aprobadas}/{a.total} A
                  </span>
                ) : (
                  <span className="flex shrink-0 gap-1">
                    {a.desaprobadas > 0 && (
                      <span className="rounded-full bg-danger-soft px-2 py-0.5 text-[11px] font-medium text-danger-fg">
                        {a.desaprobadas} con D
                      </span>
                    )}
                    {a.sin_entregar > 0 && (
                      <span className="rounded-full bg-warn-soft px-2 py-0.5 text-[11px] font-medium text-warn-fg">
                        {a.sin_entregar} sin entregar
                      </span>
                    )}
                  </span>
                )}
              </label>
            </li>
          );
        })}
      </ul>
    </article>
  );
}
