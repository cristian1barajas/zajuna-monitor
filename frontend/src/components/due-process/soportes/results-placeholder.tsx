"use client";

import { CalendarCheck, FileDown, LogIn } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const STEPS = [
  {
    icon: LogIn,
    title: "Conecta Outlook",
    text: "Inicia sesión con tu correo SENA en la ventana de Chrome que abre la app.",
  },
  {
    icon: CalendarCheck,
    title: "Elige días y etapas",
    text: "Marca las fechas en que enviaste los llamados y busca los correos.",
  },
  {
    icon: FileDown,
    title: "Descarga el ZIP",
    text: "Cada correo se imprime con Outlook y queda en una carpeta por etapa, listo para Zajuna.",
  },
];

interface ResultsPlaceholderProps {
  /** Paso en curso: 0 conectar, 1 buscar. */
  step: 0 | 1;
  searching: boolean;
}

/** Lado derecho antes de tener resultados: el recorrido en tres pasos, o la carga de la búsqueda. */
export function ResultsPlaceholder({
  step,
  searching,
}: ResultsPlaceholderProps) {
  if (searching) {
    return (
      <section
        aria-busy="true"
        aria-label="Buscando correos"
        className="rounded-xl border bg-card shadow-card"
      >
        <div className="border-b px-4 py-3">
          <Skeleton className="h-4 w-48" />
        </div>
        <div className="grid grid-cols-3 gap-px border-b">
          {[0, 1, 2].map((i) => (
            <div key={i} className="px-4 py-3">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="mt-2 h-6 w-10" />
            </div>
          ))}
        </div>
        <div className="space-y-3 p-4">
          {Array.from({ length: 7 }, (_, i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section
      aria-label="Cómo funciona"
      className="flex min-h-80 flex-col justify-center rounded-xl border border-dashed bg-card/60 p-6 sm:p-8"
    >
      <ol className="mx-auto grid w-full max-w-3xl gap-4 sm:grid-cols-3">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const current = i === step;
          const done = i < step;
          return (
            <li
              key={s.title}
              aria-current={current ? "step" : undefined}
              className={cn(
                "rounded-xl border bg-card p-4 transition-colors duration-150",
                current ? "border-primary/60 shadow-card" : "opacity-70"
              )}
            >
              <span
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold",
                  current || done
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                )}
              >
                <Icon aria-hidden="true" className="h-4 w-4" />
              </span>
              <p className="mt-3 text-sm font-semibold">
                {i + 1}. {s.title}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {s.text}
              </p>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
