import { Loader2 } from "lucide-react";

const STEPS = [
  { step: 1, label: "Autenticando en Zajuna..." },
  { step: 2, label: "Accediendo a la página de entregas..." },
  { step: 3, label: "Extrayendo datos de aprendices..." },
  { step: 4, label: "Buscando instrumento de evaluación..." },
];

/** Pasos simulados mientras el backend consulta los envíos de la tarea. */
export function LoadingSteps({ current }: { current: number }) {
  return (
    <div className="flex min-h-[300px] flex-col items-center justify-center space-y-6 rounded-xl border bg-card shadow-card px-6 py-10">
      <Loader2 aria-hidden="true" className="h-8 w-8 animate-spin text-primary" />
      <div className="w-full max-w-xs space-y-3">
        {STEPS.map(({ step, label }) => (
          <div
            key={step}
            className={`flex items-center gap-3 text-sm transition-opacity duration-500 ${
              current >= step ? "opacity-100" : "opacity-30"
            }`}
          >
            <div
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium tabular-nums ${
                current > step
                  ? "bg-ok-soft text-ok-fg"
                  : current === step
                    ? "bg-accent text-accent-foreground"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {current > step ? "✓" : step}
            </div>
            <span className={current === step ? "font-medium text-foreground" : "text-muted-foreground"}>
              {label}
            </span>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">Esto puede tardar unos segundos...</p>
    </div>
  );
}
