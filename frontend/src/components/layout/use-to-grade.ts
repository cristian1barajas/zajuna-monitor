"use client";

import { useMemo, useSyncExternalStore } from "react";
import { RESULTS_UPDATED_EVENT, storedToGrade } from "@/lib/pending-grading";

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(RESULTS_UPDATED_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(RESULTS_UPDATED_EVENT, onChange);
  };
}

/**
 * Entregas por calificar de cada ficha según su última consulta en
 * Por Calificar. Las fichas nunca consultadas no aparecen en el mapa.
 */
export function useToGradeCounts(fichas: string[]): Map<string, number> {
  const key = fichas.join(",");
  // Instantánea como texto: useSyncExternalStore exige un valor estable
  const snapshot = useSyncExternalStore(
    subscribe,
    () =>
      key
        .split(",")
        .filter(Boolean)
        .map((f) => `${f}:${storedToGrade(f) ?? ""}`)
        .join("|"),
    () => "",
  );
  return useMemo(() => {
    const map = new Map<string, number>();
    for (const part of snapshot.split("|")) {
      const [ficha, count] = part.split(":");
      if (ficha && count) map.set(ficha, Number(count));
    }
    return map;
  }, [snapshot]);
}
