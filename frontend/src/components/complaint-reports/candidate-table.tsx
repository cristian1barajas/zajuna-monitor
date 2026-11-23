"use client";

import { useState, useMemo } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import type { ComplaintCandidate } from "@/types/api";

type SortKey = "full_name" | "document" | "last_access_days" | "pending_count";
type SortDir = "asc" | "desc";

interface CandidateTableProps {
  candidates: ComplaintCandidate[];
  selected: Set<number>;
  onSelectionChange: (selected: Set<number>) => void;
}

function SortIcon({
  col,
  sortKey,
  sortDir,
}: {
  col: SortKey;
  sortKey: SortKey;
  sortDir: SortDir;
}) {
  if (sortKey !== col)
    return <ArrowUpDown className="ml-1 inline h-3.5 w-3.5 opacity-40" />;
  return sortDir === "asc" ? (
    <ArrowUp className="ml-1 inline h-3.5 w-3.5" />
  ) : (
    <ArrowDown className="ml-1 inline h-3.5 w-3.5" />
  );
}

export function CandidateTable({
  candidates,
  selected,
  onSelectionChange,
}: CandidateTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("full_name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    return [...candidates].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "full_name":
          cmp = a.full_name.localeCompare(b.full_name, "es");
          break;
        case "document":
          cmp = a.document.localeCompare(b.document);
          break;
        case "last_access_days":
          cmp = a.last_access_days - b.last_access_days;
          break;
        case "pending_count":
          cmp = a.pending_count - b.pending_count;
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [candidates, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "full_name" || key === "document" ? "asc" : "desc");
    }
  };

  const allSelected =
    candidates.length > 0 &&
    candidates.every((c) => selected.has(c.user_id));

  const toggleAll = () => {
    if (allSelected) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(candidates.map((c) => c.user_id)));
    }
  };

  const toggle = (userId: number) => {
    const next = new Set(selected);
    if (next.has(userId)) {
      next.delete(userId);
    } else {
      next.add(userId);
    }
    onSelectionChange(next);
  };

  if (candidates.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-card shadow-card p-8 text-center text-sm text-muted-foreground">
        No se encontraron candidatos con los filtros seleccionados
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border bg-card shadow-card">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50 text-xs text-muted-foreground">
            <th className="w-10 p-3">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                aria-label="Seleccionar todos los candidatos"
                className="rounded"
              />
            </th>
            <th
              className="cursor-pointer p-3 text-left font-medium select-none hover:text-primary"
              onClick={() => toggleSort("full_name")}
            >
              Aprendiz
              <SortIcon col="full_name" sortKey={sortKey} sortDir={sortDir} />
            </th>
            <th
              className="cursor-pointer p-3 text-left font-medium select-none hover:text-primary"
              onClick={() => toggleSort("document")}
            >
              Cédula
              <SortIcon col="document" sortKey={sortKey} sortDir={sortDir} />
            </th>
            <th
              className="cursor-pointer p-3 text-center font-medium select-none hover:text-primary"
              onClick={() => toggleSort("last_access_days")}
            >
              Días inactivo
              <SortIcon col="last_access_days" sortKey={sortKey} sortDir={sortDir} />
            </th>
            <th
              className="cursor-pointer p-3 text-center font-medium select-none hover:text-primary"
              onClick={() => toggleSort("pending_count")}
            >
              Pendientes
              <SortIcon col="pending_count" sortKey={sortKey} sortDir={sortDir} />
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => (
            <tr
              key={c.user_id}
              className="border-b transition-colors duration-150 ease-out last:border-0 hover:bg-muted/60"
            >
              <td className="p-3">
                <input
                  type="checkbox"
                  checked={selected.has(c.user_id)}
                  onChange={() => toggle(c.user_id)}
                  aria-label={`Seleccionar a ${c.full_name}`}
                  className="rounded"
                />
              </td>
              <td className="p-3">
                <div>
                  <p className="font-medium text-foreground">{c.full_name}</p>
                  <p className="text-xs text-muted-foreground">{c.email}</p>
                </div>
              </td>
              <td className="p-3 font-mono text-sm tabular-nums text-muted-foreground">
                {c.document}
              </td>
              <td className="p-3 text-center">
                <span className="inline-flex items-center rounded-full border border-danger-border bg-danger-soft px-2 py-0.5 text-xs font-medium tabular-nums text-danger-fg">
                  {c.last_access_days === 9999 ? "Nunca" : `${c.last_access_days}d`}
                </span>
              </td>
              <td className="p-3 text-center">
                <span className="inline-flex items-center rounded-full border border-warn-border bg-warn-soft px-2 py-0.5 text-xs font-medium tabular-nums text-warn-fg">
                  {c.pending_count} / {c.total_selected}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
