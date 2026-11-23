import { Badge } from "@/components/ui/badge";

const RESULTADO_CONFIG: Record<string, { label: string; className: string }> = {
  listo_para_aprobar: {
    label: "Listo para Aprobar",
    className: "bg-info-soft text-info-fg border-info-border",
  },
  correcto: {
    label: "Correcto",
    className: "bg-ok-soft text-ok-fg border-ok-border",
  },
  pendiente: {
    label: "Pendiente",
    className: "bg-pending-soft text-pending-fg border-pending-border",
  },
  con_problemas: {
    label: "Con Problemas",
    className: "bg-warn-soft text-warn-fg border-warn-border",
  },
  inconsistencia: {
    label: "Inconsistencia",
    className: "bg-danger-soft text-danger-fg border-danger-border",
  },
  aprobado_anticipado: {
    label: "Aprobado Anticipado",
    className: "bg-notice-soft text-notice-fg border-notice-border",
  },
};

interface RapStatusBadgeProps {
  resultado: string;
  compact?: boolean;
}

export function RapStatusBadge({ resultado, compact }: RapStatusBadgeProps) {
  const config = RESULTADO_CONFIG[resultado] ?? {
    label: resultado,
    className: "bg-pending-soft text-pending-fg border-pending-border",
  };

  return (
    <Badge
      variant="outline"
      className={`whitespace-nowrap font-medium ${config.className} ${compact ? "px-1.5 py-0 text-[10px]" : ""}`}
    >
      {config.label}
    </Badge>
  );
}

/** Human-readable label for a resultado key */
export function resultadoLabel(resultado: string): string {
  return RESULTADO_CONFIG[resultado]?.label ?? resultado;
}

/** Color for heatmap cells */
export function resultadoColor(resultado: string): string {
  switch (resultado) {
    case "listo_para_aprobar":
      return "bg-info";
    case "correcto":
      return "bg-ok";
    case "pendiente":
      return "bg-pending";
    case "con_problemas":
      return "bg-warn";
    case "inconsistencia":
      return "bg-danger";
    case "aprobado_anticipado":
      return "bg-notice";
    default:
      return "bg-pending-soft";
  }
}
