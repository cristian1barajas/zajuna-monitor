import type { StudentCrossResult } from "@/types/api";

/** Estado de RAP (clave del resumen) → contador del aprendiz con ese estado. */
export const STATUS_COUNT_FIELD = {
  listo_para_aprobar: "listos_para_aprobar",
  correcto: "correctos",
  pendiente: "pendientes",
  con_problemas: "con_problemas",
  inconsistencia: "inconsistencias",
  aprobado_anticipado: "aprobados_anticipados",
} as const satisfies Record<string, keyof StudentCrossResult>;

export type RapStatus = keyof typeof STATUS_COUNT_FIELD;

/** Requiere acción: algún RAP listo para aprobar, con problemas o inconsistente. */
export function needsAction(s: StudentCrossResult): boolean {
  return s.listos_para_aprobar > 0 || s.con_problemas > 0 || s.inconsistencias > 0;
}

export function hasStatus(s: StudentCrossResult, status: RapStatus): boolean {
  return s[STATUS_COUNT_FIELD[status]] > 0;
}
