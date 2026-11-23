"use client";

import type { SubmissionInfo } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/** Envíos que se descargan: estado elegido, con archivos y sin los ya calificados. */
export function downloadableSubmissions(
  submissions: SubmissionInfo[],
  selectedStatuses: Set<string>,
): SubmissionInfo[] {
  return submissions.filter(
    (s) =>
      selectedStatuses.has(s.status) &&
      s.file_count > 0 &&
      !(s.status === "Enviado para calificar" && s.is_graded),
  );
}

interface SubmissionsTableProps {
  submissions: SubmissionInfo[];
}

/** Tabla a todo el ancho de los envíos que se van a descargar. */
export function SubmissionsTable({ submissions }: SubmissionsTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Aprendiz</TableHead>
          <TableHead className="hidden sm:table-cell">Cédula</TableHead>
          <TableHead>Estado</TableHead>
          <TableHead className="w-24 text-center">Archivos</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {submissions.map((sub) => (
          <TableRow key={sub.user_id}>
            <TableCell className="max-w-0">
              <p className="truncate font-medium text-foreground">{sub.full_name}</p>
              <p className="truncate text-xs text-muted-foreground">{sub.email}</p>
            </TableCell>
            <TableCell className="hidden font-mono text-sm tabular-nums text-muted-foreground sm:table-cell">
              {sub.document}
            </TableCell>
            <TableCell>
              <Badge
                variant="outline"
                className={
                  sub.is_graded
                    ? "border-ok-border bg-ok-soft text-ok-fg"
                    : "border-warn-border bg-warn-soft text-warn-fg"
                }
              >
                {sub.is_graded ? "Calificado" : sub.status}
              </Badge>
            </TableCell>
            <TableCell className="text-center text-sm font-semibold tabular-nums text-foreground">
              {sub.file_count}
            </TableCell>
          </TableRow>
        ))}
        {submissions.length === 0 && (
          <TableRow>
            <TableCell colSpan={4} className="py-10 text-center text-sm text-muted-foreground">
              No hay envíos con archivos en los estados elegidos
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
