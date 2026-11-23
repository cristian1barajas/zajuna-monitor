"use client";

import { useState, useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ArrowUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StudentItem } from "@/types/api";

interface StudentTableProps {
  students: StudentItem[];
}

type SortKey = "full_name" | "document" | "approved" | "disapproved" | "pending";
type SortDir = "asc" | "desc";

function SortableHeader({
  label,
  field,
  onSort,
  className,
}: {
  label: string;
  field: SortKey;
  onSort: (field: SortKey) => void;
  className?: string;
}) {
  const numeric = className?.includes("text-right");
  return (
    <TableHead
      className={cn(
        "cursor-pointer select-none transition-colors duration-150 ease-out hover:bg-muted/50",
        className
      )}
      onClick={() => onSort(field)}
    >
      <div className={cn("flex items-center gap-1", numeric && "justify-end")}>
        {label}
        <ArrowUpDown
          aria-hidden="true"
          className="h-3 w-3 text-muted-foreground"
        />
      </div>
    </TableHead>
  );
}

export function StudentTable({ students }: StudentTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("pending");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [search, setSearch] = useState("");

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    let result = students;
    if (q) {
      result = result.filter(
        (s) =>
          s.full_name.toLowerCase().includes(q) ||
          s.document.includes(q)
      );
    }
    result = [...result].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string") {
        return sortDir === "asc"
          ? (av as string).localeCompare(bv as string)
          : (bv as string).localeCompare(av as string);
      }
      return sortDir === "asc"
        ? (av as number) - (bv as number)
        : (bv as number) - (av as number);
    });
    return result;
  }, [students, sortKey, sortDir, search]);

  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-card">
      {/* Cabecera de sección: título + contador integrado y búsqueda */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">
          Aprendices{" "}
          <span className="font-normal tabular-nums text-muted-foreground">
            {filtered.length} de {students.length}
          </span>
        </h2>
        <input
          type="text"
          placeholder="Buscar por nombre o cedula..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-8 w-full rounded-md border bg-background px-3 text-sm text-foreground transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring sm:w-64"
        />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <SortableHeader
              label="Nombre"
              field="full_name"
              onSort={toggleSort}
              className="pl-4"
            />
            <SortableHeader label="Cedula" field="document" onSort={toggleSort} />
            <SortableHeader
              label="Aprobados"
              field="approved"
              onSort={toggleSort}
              className="text-right"
            />
            <SortableHeader
              label="Desaprobados"
              field="disapproved"
              onSort={toggleSort}
              className="text-right"
            />
            <SortableHeader
              label="Pendientes"
              field="pending"
              onSort={toggleSort}
              className="pr-4 text-right"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((s) => (
            <TableRow
              key={s.user_id}
              className="transition-colors duration-150 ease-out"
            >
              <TableCell className="pl-4 font-medium">{s.full_name}</TableCell>
              <TableCell className="tabular-nums text-muted-foreground">
                {s.document}
              </TableCell>
              <TableCell className="text-right font-semibold tabular-nums text-ok-fg">
                {s.approved}
              </TableCell>
              <TableCell
                className={cn(
                  "text-right font-semibold tabular-nums",
                  s.disapproved > 0 ? "text-danger-fg" : "text-muted-foreground"
                )}
              >
                {s.disapproved}
              </TableCell>
              <TableCell className="pr-4 text-right font-semibold tabular-nums text-muted-foreground">
                {s.pending}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}
