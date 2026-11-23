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
import type { ParticipantItem } from "@/types/api";

interface ActivityTableProps {
  participants: ParticipantItem[];
}

type SortKey = "full_name" | "document" | "last_access_days" | "status";
type SortDir = "asc" | "desc";
type View = "inactivos" | "recientes" | "todos";

// 9999 = nunca entró y cuenta como inactivo 30+. Solo se vigilan los activos.
function bucketOf(p: ParticipantItem): Exclude<View, "todos"> | null {
  if (p.status !== "Activo") return null;
  if (p.last_access_days >= 30) return "inactivos";
  if (p.last_access_days >= 7) return "recientes";
  return null;
}

const EMPTY_MESSAGE: Record<View, string> = {
  inactivos: "Ningún aprendiz activo lleva 30 días o más sin entrar",
  recientes: "Ningún aprendiz activo lleva entre 7 y 29 días sin entrar",
  todos: "Ningún aprendiz coincide con la búsqueda",
};

function inactivityColor(days: number): string {
  if (days === 9999) return "text-danger-fg font-semibold";
  if (days >= 30) return "text-danger-fg";
  if (days >= 7) return "text-warn-fg";
  return "text-ok-fg";
}

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
  return (
    <TableHead
      className={cn(
        "cursor-pointer select-none transition-colors duration-150 ease-out hover:bg-muted/50",
        className
      )}
      onClick={() => onSort(field)}
    >
      <div className="flex items-center gap-1">
        {label}
        <ArrowUpDown
          aria-hidden="true"
          className="h-3 w-3 text-muted-foreground"
        />
      </div>
    </TableHead>
  );
}

export function ActivityTable({ participants }: ActivityTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("last_access_days");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<View>("inactivos");

  const counts = useMemo(() => {
    const c: Record<View, number> = { inactivos: 0, recientes: 0, todos: participants.length };
    for (const p of participants) {
      const b = bucketOf(p);
      if (b) c[b]++;
    }
    return c;
  }, [participants]);

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
    let result = participants;

    if (view !== "todos") {
      result = result.filter((p) => bucketOf(p) === view);
    }

    if (q) {
      result = result.filter(
        (p) =>
          p.full_name.toLowerCase().includes(q) ||
          p.document.includes(q) ||
          p.email.toLowerCase().includes(q)
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
  }, [participants, sortKey, sortDir, search, view]);

  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div
          role="radiogroup"
          aria-label="Qué mostrar"
          className="inline-flex flex-wrap rounded-full border p-0.5"
        >
          {(
            [
              ["inactivos", `Inactivos 30+ días (${counts.inactivos})`],
              ["recientes", `7 a 29 días (${counts.recientes})`],
              ["todos", `Todos (${counts.todos})`],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={view === value}
              onClick={() => setView(value)}
              className={cn(
                "h-7 rounded-full px-3 text-xs font-medium transition-colors duration-150 ease-out",
                view === value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <input
          type="search"
          aria-label="Buscar aprendiz"
          placeholder="Buscar por nombre, cédula o email"
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
            <SortableHeader
              label="Cédula"
              field="document"
              onSort={toggleSort}
              className="hidden sm:table-cell"
            />
            <TableHead className="hidden xl:table-cell">Email</TableHead>
            <SortableHeader
              label="Último acceso"
              field="last_access_days"
              onSort={toggleSort}
            />
            <SortableHeader
              label="Estatus"
              field="status"
              onSort={toggleSort}
              className="pr-4"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((p) => (
            <TableRow
              key={p.user_id}
              className="transition-colors duration-150 ease-out"
            >
              <TableCell className="pl-4 font-medium">{p.full_name}</TableCell>
              <TableCell className="hidden tabular-nums text-muted-foreground sm:table-cell">
                {p.document}
              </TableCell>
              <TableCell className="hidden text-xs text-muted-foreground xl:table-cell">
                {p.email}
              </TableCell>
              <TableCell>
                <span
                  className={cn("tabular-nums", inactivityColor(p.last_access_days))}
                >
                  {p.last_access_days === 9999
                    ? "Nunca"
                    : p.last_access_days === 0
                      ? p.last_access_raw
                      : `${p.last_access_days} días`}
                </span>
              </TableCell>
              <TableCell className="pr-4">
                <span
                  className={cn(
                    "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
                    p.status === "Activo"
                      ? "border-ok-border bg-ok-soft text-ok-fg"
                      : "border-danger-border bg-danger-soft text-danger-fg"
                  )}
                >
                  {p.status}
                </span>
              </TableCell>
            </TableRow>
          ))}
          {filtered.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                {search ? EMPTY_MESSAGE.todos : EMPTY_MESSAGE[view]}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </section>
  );
}
