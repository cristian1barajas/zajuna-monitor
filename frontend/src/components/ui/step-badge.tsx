import { cn } from "@/lib/utils";

/** Número de paso en círculo (stepper estilo SI Contratista). */
export function StepBadge({ n, className }: { n: number; className?: string }) {
  return (
    <span
      aria-label={`Paso ${n}`}
      className={cn(
        "inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sena-teal text-xs font-bold tabular-nums text-white",
        className
      )}
    >
      {n}
    </span>
  );
}
