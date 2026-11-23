"use client";

/**
 * Franja de bienvenida del dashboard (teal estilo SI Contratista): saludo,
 * tres indicadores sin íconos (decisión D2) y el avance global, en una sola
 * línea para que la tabla de fichas quede a la vista.
 */

import { useEffect, useState } from "react";
import { getMe, getAccessToken } from "@/lib/cmm-auth";

interface StatsOverviewProps {
  totalFichas: number;
  totalStudents: number;
  totalPending: number;
  overallCompletion: number;
}

function greetingForHour(hour: number): string {
  if (hour < 12) return "Buenos días";
  if (hour < 19) return "Buenas tardes";
  return "Buenas noches";
}

export function StatsOverview({
  totalFichas,
  totalStudents,
  totalPending,
  overallCompletion,
}: StatsOverviewProps) {
  const [firstName, setFirstName] = useState<string | null>(null);

  // Nombre del instructor para el saludo (mismo patrón que UserBadge)
  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    getMe(token)
      .then((user) => setFirstName(user.full_name.split(" ")[0] ?? null))
      .catch(() => {});
  }, []);

  const greeting = greetingForHour(new Date().getHours());

  // La cifra ya está en el indicador; la frase solo aclara qué significa
  const contextLine =
    totalPending > 0
      ? "“Sin nota” incluye trabajos aún no enviados. Lo que espera tu calificación sale en la columna Por calificar."
      : "Todas las notas de tus fichas activas están registradas.";

  const kpis = [
    { label: "Fichas", value: String(totalFichas), highlight: false },
    {
      label: "Aprendices activos",
      value: totalStudents.toLocaleString(),
      highlight: false,
    },
    {
      label: "Sin nota",
      value: totalPending.toLocaleString(),
      highlight: totalPending > 0,
    },
  ] as const;

  return (
    <section
      aria-label="Resumen del instructor"
      className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-sena-teal-deep via-sena-teal to-sena-teal-light text-on-teal shadow-card"
    >
      <HeroPattern />
      {/* Una sola franja: el hero ya no empuja la lista de fichas fuera de la pantalla */}
      <div className="relative flex flex-wrap items-center gap-x-8 gap-y-4 px-5 py-4 sm:px-6">
        <div className="min-w-0 flex-1 basis-64">
          <p className="text-lg font-bold leading-tight tracking-tight text-white">
            {greeting}
            {firstName ? `, ${firstName}` : ""}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-on-teal">{contextLine}</p>
        </div>

        <dl className="flex gap-6 sm:gap-8">
          {kpis.map((kpi) => (
            <div key={kpi.label}>
              <dt className="text-[11px] text-on-teal-muted">{kpi.label}</dt>
              <dd
                className={`text-xl font-bold tabular-nums tracking-tight ${
                  kpi.highlight ? "text-sena-yellow" : "text-white"
                }`}
              >
                {kpi.value}
              </dd>
            </div>
          ))}
        </dl>

        <div className="w-full sm:w-48">
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-[11px] text-on-teal-muted">Avance global</p>
            <p className="text-xl font-bold tabular-nums tracking-tight text-white">
              {overallCompletion}
              <span className="text-sm font-semibold text-on-teal-muted">%</span>
            </p>
          </div>
          <div
            role="progressbar"
            aria-label="Avance global de calificación"
            aria-valuenow={overallCompletion}
            aria-valuemin={0}
            aria-valuemax={100}
            className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-white/15"
          >
            <div
              className="h-full rounded-full bg-sena-green-light"
              style={{ width: `${Math.min(overallCompletion, 100)}%` }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

/** Patrón de marca decorativo (D4: sin fotos): arcos concéntricos a la derecha. */
function HeroPattern() {
  return (
    <svg
      aria-hidden="true"
      className="pointer-events-none absolute -right-16 -top-40 h-[320px] w-[320px] text-white/[0.06]"
      viewBox="0 0 420 420"
      fill="none"
    >
      {[60, 110, 160, 210].map((r) => (
        <circle key={r} cx="210" cy="210" r={r} stroke="currentColor" strokeWidth="28" />
      ))}
    </svg>
  );
}
