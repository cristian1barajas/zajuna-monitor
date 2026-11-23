"use client";

import { TableCell, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ChevronDown, ChevronRight, CheckCircle2, X } from "lucide-react";
import { StageBadge } from "@/components/due-process/stage-badge";
import type { StudentReportItem } from "@/types/api";

function statusBadgeClass(status: string) {
  if (status === "Activo")
    return "border-ok-border bg-ok-soft text-ok-fg hover:bg-ok-soft";
  if (status === "Suspendido")
    return "border-danger-border bg-danger-soft text-danger-fg hover:bg-danger-soft";
  return "border-pending-border bg-pending-soft text-pending-fg hover:bg-pending-soft";
}

function daysColor(days: number) {
  if (days <= 7) return "text-ok-fg";
  if (days <= 30) return "text-warn-fg";
  return "text-danger-fg";
}

/** Pill "Novedad" junto al nombre, con botón opcional para quitarla. */
function NovedadPill({
  userId,
  onRemoveNovedad,
}: {
  userId: number;
  onRemoveNovedad?: (userId: number) => void;
}) {
  return (
    <span className="inline-flex items-center gap-0.5 rounded-full bg-caution-soft pl-1.5 pr-0.5 py-0.5 text-[10px] font-medium text-caution-fg border border-caution-border">
      Novedad
      {onRemoveNovedad && (
        <button
          onClick={() => onRemoveNovedad(userId)}
          className="ml-0.5 rounded-full p-0.5 hover:bg-caution/20"
          title="Quitar novedad"
        >
          <X className="h-2.5 w-2.5" />
        </button>
      )}
    </span>
  );
}

/** Detalle expandible con las evidencias pendientes del aprendiz. */
function OverdueEvidencesDetail({ student }: { student: StudentReportItem }) {
  return (
    <div className="mt-2 space-y-1 rounded-md bg-muted/50 p-2">
      <p className="text-xs font-medium text-muted-foreground">
        Evidencias pendientes:
      </p>
      {student.overdue_evidences.map((ev, i) => (
        <div
          key={ev.item_id}
          className="flex items-center gap-2 text-xs"
        >
          <span className="text-muted-foreground">
            {i + 1}.
          </span>
          <span>{ev.name}</span>
          <Badge
            variant="outline"
            className="text-[10px]"
          >
            {ev.category}
          </Badge>
        </div>
      ))}
    </div>
  );
}

/** Badge de la columna "Pendientes" según el estado del aprendiz. */
function OverdueCountBadge({
  student,
  isAlDia,
  hasNovedad,
  isSuspended,
}: {
  student: StudentReportItem;
  isAlDia: boolean;
  hasNovedad: boolean;
  isSuspended: boolean;
}) {
  if (isSuspended) {
    return (
      <Badge className="bg-danger-soft text-danger-fg hover:bg-danger-soft border-danger-border">
        Suspendido
      </Badge>
    );
  }
  if (hasNovedad) {
    return (
      <Badge className="bg-caution-soft text-caution-fg hover:bg-caution-soft border-caution-border">
        Novedad
      </Badge>
    );
  }
  if (isAlDia) {
    return (
      <Badge className="bg-ok-soft text-ok-fg hover:bg-ok-soft border-ok-border">
        Al dia
      </Badge>
    );
  }
  return (
    <Badge
      variant={student.overdue_count > 5 ? "destructive" : "secondary"}
      className="tabular-nums"
    >
      {student.overdue_count}
    </Badge>
  );
}

interface OverdueStudentRowProps {
  student: StudentReportItem;
  isExpanded: boolean;
  isSelected: boolean;
  hasNovedad: boolean;
  dueProcessStage: string;
  onToggleExpand: (userId: number) => void;
  onToggleSelect: (userId: number) => void;
  onRemoveNovedad?: (userId: number) => void;
}

/** Fila de aprendiz: selección, expansión de evidencias y badges de estado. */
export function OverdueStudentRow({
  student,
  isExpanded,
  isSelected,
  hasNovedad,
  dueProcessStage,
  onToggleExpand,
  onToggleSelect,
  onRemoveNovedad,
}: OverdueStudentRowProps) {
  const isAlDia = student.overdue_count === 0;
  const isSuspended = student.status === "Suspendido";
  return (
    <TableRow
      className={
        isSuspended
          ? "bg-danger-soft/50 opacity-50"
          : hasNovedad
            ? "bg-caution-soft/50 opacity-60"
            : isAlDia
              ? "bg-ok-soft/50"
              : ""
      }
    >
      <TableCell>
        {!isAlDia && !hasNovedad && student.status !== "Suspendido" && (
          <Checkbox
            checked={isSelected}
            onCheckedChange={() => onToggleSelect(student.user_id)}
          />
        )}
      </TableCell>
      <TableCell>
        {!isAlDia && student.overdue_count > 0 ? (
          <button
            onClick={() => onToggleExpand(student.user_id)}
            aria-expanded={isExpanded}
            aria-label={`Ver evidencias pendientes de ${student.full_name}`}
            className="rounded p-0.5 transition-colors duration-150 ease-out hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        ) : (
          <CheckCircle2 className="h-4 w-4 text-ok-fg" />
        )}
      </TableCell>
      <TableCell>
        <div>
          <div className="flex items-center gap-2">
            <p
              className={`font-medium ${
                hasNovedad
                  ? "text-caution-fg"
                  : isAlDia
                    ? "text-ok-fg"
                    : ""
              }`}
            >
              {student.full_name}
            </p>
            {hasNovedad && (
              <NovedadPill
                userId={student.user_id}
                onRemoveNovedad={onRemoveNovedad}
              />
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {student.email}
          </p>
          {/* Mobile-only extra info */}
          <div className="mt-1 flex flex-wrap gap-2 sm:hidden">
            <span className="font-mono text-xs tabular-nums text-muted-foreground">
              {student.document}
            </span>
            <Badge
              className={`${statusBadgeClass(student.status)} h-4 text-[10px]`}
            >
              {student.status}
            </Badge>
          </div>
          {isExpanded && !isAlDia && (
            <OverdueEvidencesDetail student={student} />
          )}
        </div>
      </TableCell>
      <TableCell className="hidden font-mono text-sm tabular-nums sm:table-cell">
        {student.document}
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Badge
          className={`${statusBadgeClass(student.status)} text-xs`}
        >
          {student.status}
        </Badge>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <span
          className={`text-sm font-medium tabular-nums ${daysColor(student.last_access_days)}`}
        >
          {student.last_access_days === 9999
            ? "Nunca"
            : student.last_access_days === 0
              ? "Hoy"
              : `${student.last_access_days}d`}
        </span>
        <p className="text-xs text-muted-foreground">
          {student.last_access_raw}
        </p>
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <StageBadge stage={dueProcessStage} />
      </TableCell>
      <TableCell className="text-center">
        <OverdueCountBadge
          student={student}
          isAlDia={isAlDia}
          hasNovedad={hasNovedad}
          isSuspended={isSuspended}
        />
      </TableCell>
    </TableRow>
  );
}
