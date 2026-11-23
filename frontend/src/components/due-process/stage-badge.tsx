"use client";

const STAGE_CONFIG: Record<string, { label: string; color: string }> = {
  sin_proceso: {
    label: "Sin proceso",
    color: "bg-ok-soft text-ok-fg border-ok-border",
  },
  primer_llamado: {
    label: "1er llamado",
    color: "bg-warn-soft text-warn-fg border-warn-border",
  },
  segundo_llamado: {
    label: "2do llamado",
    color: "bg-caution-soft text-caution-fg border-caution-border",
  },
  tercer_llamado: {
    label: "3er llamado",
    color: "bg-caution-soft text-caution-fg border-caution-border",
  },
  plan_mejoramiento: {
    label: "Plan mejoramiento",
    color: "bg-danger-soft text-danger-fg border-danger-border",
  },
  comite: {
    label: "Comité",
    color: "bg-danger-fg text-white border-danger-fg dark:text-background",
  },
};

interface StageBadgeProps {
  stage: string;
  className?: string;
}

export function StageBadge({ stage, className = "" }: StageBadgeProps) {
  const config = STAGE_CONFIG[stage] ?? {
    label: stage,
    color: "bg-pending-soft text-pending-fg border-pending-border",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${config.color} ${className}`}
    >
      {config.label}
    </span>
  );
}
