/**
 * Colores de estado en hex para superficies donde las variables CSS
 * no resuelven (exportación PDF/print, canvas). Valores del tema claro
 * porque los exports se imprimen sobre blanco.
 *
 * Fuente: SENA Design System (Brandbook 2022) — mismos valores que los
 * tokens --status-* de globals.css. Si cambian allá, cambian acá.
 */

export const SENA = {
  green: "#39A900",
  greenDark: "#2B7A00",
  navy: "#00324D",
  beige: "#FBFBE2",
  deepGreen: "#385C57",
  coral: "#CB7766",
  coralDark: "#A4513B",
  yellow: "#FFCE40",
  sky: "#82DEF0",
} as const;

export type StatusFamily =
  | "ok"
  | "warn"
  | "caution"
  | "danger"
  | "info"
  | "notice"
  | "pending";

export const STATUS_HEX: Record<
  StatusFamily,
  { solid: string; soft: string; fg: string; border: string }
> = {
  ok: { solid: "#39A900", soft: "#EBF7E0", fg: "#2B7A00", border: "#C9EAB0" },
  warn: { solid: "#FFCE40", soft: "#FFF4D1", fg: "#8A6D00", border: "#F0DFA0" },
  caution: { solid: "#D98E36", soft: "#F9EDDC", fg: "#935B10", border: "#EDD3AE" },
  danger: { solid: "#CB7766", soft: "#F9ECE8", fg: "#A4513B", border: "#ECCFC6" },
  info: { solid: "#82DEF0", soft: "#E9F8FC", fg: "#17677D", border: "#BCE9F4" },
  notice: { solid: "#00324D", soft: "#E8F0F5", fg: "#00324D", border: "#C3D6E2" },
  pending: { solid: "#B5B5B5", soft: "#F2F2F2", fg: "#6B6B6B", border: "#D4D4D4" },
};

/** Familia de estado para cada resultado del cruce RAP (juicios). */
export const RAP_STATUS_FAMILY: Record<string, StatusFamily> = {
  listo_para_aprobar: "info",
  correcto: "ok",
  pendiente: "pending",
  con_problemas: "warn",
  inconsistencia: "danger",
  aprobado_anticipado: "notice",
};

/** Hex de celda para exportación PDF del cruce RAP. */
export function rapResultadoHex(resultado: string): string {
  const family = RAP_STATUS_FAMILY[resultado];
  return family ? STATUS_HEX[family].solid : STATUS_HEX.pending.soft;
}

/** Hex del semáforo del grader (A / D / entregada sin calificar / vacía). */
export function gradeHex(value: string, isSubmitted = false): string {
  if (value === "A") return STATUS_HEX.ok.solid;
  if (value === "D") return STATUS_HEX.danger.solid;
  return isSubmitted ? STATUS_HEX.warn.solid : STATUS_HEX.pending.solid;
}
