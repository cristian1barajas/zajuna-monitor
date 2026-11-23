"use client";

import { TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import type { SortField, SortDir } from "@/lib/overdue-students";

function SortIcon({
  field,
  sortField,
  sortDir,
}: {
  field: SortField;
  sortField: SortField;
  sortDir: SortDir;
}) {
  if (sortField !== field) return <ArrowUpDown className="h-3 w-3 opacity-40" />;
  return sortDir === "asc" ? (
    <ArrowUp className="h-3 w-3" />
  ) : (
    <ArrowDown className="h-3 w-3" />
  );
}

interface OverdueTableHeaderProps {
  sortField: SortField;
  sortDir: SortDir;
  onSort: (field: SortField) => void;
  allSelected: boolean;
  onToggleAll: () => void;
}

/** Encabezado de la tabla con columnas ordenables y checkbox global. */
export function OverdueTableHeader({
  sortField,
  sortDir,
  onSort,
  allSelected,
  onToggleAll,
}: OverdueTableHeaderProps) {
  return (
    <TableHeader>
      <TableRow>
        <TableHead className="w-10">
          <Checkbox
            checked={allSelected}
            onCheckedChange={onToggleAll}
            aria-label="Seleccionar todos los aprendices"
          />
        </TableHead>
        <TableHead className="w-8" />
        <TableHead>
          <button
            onClick={() => onSort("full_name")}
            className="flex items-center gap-1 rounded transition-colors duration-150 ease-out hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Aprendiz
            <SortIcon field="full_name" sortField={sortField} sortDir={sortDir} />
          </button>
        </TableHead>
        <TableHead className="w-28 hidden sm:table-cell">
          <button
            onClick={() => onSort("document")}
            className="flex items-center gap-1 rounded transition-colors duration-150 ease-out hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Cédula
            <SortIcon field="document" sortField={sortField} sortDir={sortDir} />
          </button>
        </TableHead>
        <TableHead className="w-28 hidden md:table-cell">
          <button
            onClick={() => onSort("status")}
            className="flex items-center gap-1 rounded transition-colors duration-150 ease-out hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Estado
            <SortIcon field="status" sortField={sortField} sortDir={sortDir} />
          </button>
        </TableHead>
        <TableHead className="w-28 hidden md:table-cell">
          <button
            onClick={() => onSort("last_access_days")}
            className="flex items-center gap-1 rounded transition-colors duration-150 ease-out hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Inactividad
            <SortIcon field="last_access_days" sortField={sortField} sortDir={sortDir} />
          </button>
        </TableHead>
        <TableHead className="w-28 hidden lg:table-cell">Proceso</TableHead>
        <TableHead className="w-24 text-center">
          <button
            onClick={() => onSort("overdue_count")}
            className="flex items-center justify-center gap-1 rounded transition-colors duration-150 ease-out hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Pendientes
            <SortIcon field="overdue_count" sortField={sortField} sortDir={sortDir} />
          </button>
        </TableHead>
      </TableRow>
    </TableHeader>
  );
}
