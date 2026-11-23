"use client";

import { useState, useMemo } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Search, X } from "lucide-react";
import type { StudentItem, NovedadRecord } from "@/types/api";

interface NovedadesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  students: StudentItem[];
  novedadRecords: NovedadRecord[];
  onAdd: (userIds: number[]) => Promise<void>;
  onRemove: (userIds: number[]) => Promise<void>;
}

/** Marca o quita la novedad (cancelación en proceso) de los aprendices activos. */
export function NovedadesDialog({
  open,
  onOpenChange,
  students,
  novedadRecords,
  onAdd,
  onRemove,
}: NovedadesDialogProps) {
  const [search, setSearch] = useState("");
  const [pending, setPending] = useState(false);

  const novedadIds = useMemo(
    () => new Set(novedadRecords.map((r) => r.user_id)),
    [novedadRecords],
  );

  // Only show active students (suspended are already officially cancelled)
  const activeStudents = useMemo(
    () => students.filter((s) => s.status === "Activo"),
    [students],
  );

  const filteredStudents = useMemo(() => {
    if (!search.trim()) return activeStudents;
    const q = search.toLowerCase().trim();
    return activeStudents.filter(
      (s) =>
        s.full_name.toLowerCase().includes(q) ||
        s.document.includes(q),
    );
  }, [activeStudents, search]);

  const suspendedCount = students.length - activeStudents.length;

  const handleToggle = async (userId: number) => {
    setPending(true);
    try {
      if (novedadIds.has(userId)) {
        await onRemove([userId]);
      } else {
        await onAdd([userId]);
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={`Novedades${novedadRecords.length ? ` (${novedadRecords.length})` : ""}`}
        subtitle="Marca los aprendices activos con cancelación en proceso u otra novedad. Se excluyen de correos, reportes PDF y debido proceso."
        className="max-w-xl"
        footer={
          <>
            {novedadRecords.length > 0 ? (
              <button
                onClick={() => onRemove(Array.from(novedadIds))}
                disabled={pending}
                className="rounded text-xs font-medium text-muted-foreground transition-colors duration-150 ease-out hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
              >
                Quitar todas
              </button>
            ) : (
              <span />
            )}
            <Button onClick={() => onOpenChange(false)}>Listo</Button>
          </>
        }
      >
        <div className="space-y-3 px-6 py-4">
          {suspendedCount > 0 && (
            <p className="text-xs tabular-nums text-danger-fg">
              {suspendedCount === 1
                ? "1 aprendiz ya suspendido oficialmente (no aparece aquí)"
                : `${suspendedCount} aprendices ya suspendidos oficialmente (no aparecen aquí)`}
            </p>
          )}

          {/* Search */}
          <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
            />
            <input
              type="text"
              placeholder="Buscar aprendiz"
              aria-label="Buscar aprendiz"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-full rounded-md border border-input bg-background pl-7 pr-7 text-xs text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground/70 focus:border-sena-green focus:ring-2 focus:ring-ring/30"
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                aria-label="Limpiar búsqueda"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors duration-150 ease-out hover:text-foreground"
              >
                <X aria-hidden="true" className="h-3 w-3" />
              </button>
            )}
          </div>

          {/* Student list */}
          <div className="space-y-0.5">
            {filteredStudents.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                No se encontraron aprendices
              </p>
            ) : (
              filteredStudents.map((student) => {
                const hasNovedad = novedadIds.has(student.user_id);
                return (
                  <label
                    key={student.user_id}
                    className={`flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 transition-colors duration-150 ease-out hover:bg-muted/70 ${
                      hasNovedad ? "bg-caution-soft" : ""
                    } ${pending ? "pointer-events-none opacity-60" : ""}`}
                  >
                    <Checkbox
                      checked={hasNovedad}
                      onCheckedChange={() => handleToggle(student.user_id)}
                      aria-label={`Novedad de ${student.full_name}`}
                      className={
                        hasNovedad
                          ? "border-caution data-[state=checked]:border-caution data-[state=checked]:bg-caution"
                          : ""
                      }
                    />
                    <div className="min-w-0 flex-1">
                      <p
                        className={`truncate text-xs ${
                          hasNovedad
                            ? "font-medium text-caution-fg"
                            : "text-foreground"
                        }`}
                      >
                        {student.full_name}
                      </p>
                      <p className="truncate text-[11px] tabular-nums text-muted-foreground">
                        {student.document}
                      </p>
                    </div>
                    {hasNovedad && (
                      <span className="shrink-0 text-[11px] font-medium text-caution-fg">
                        Novedad
                      </span>
                    )}
                  </label>
                );
              })
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
