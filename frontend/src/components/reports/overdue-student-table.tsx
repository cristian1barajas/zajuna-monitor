"use client";

import { useState, useMemo } from "react";
import { Table, TableBody } from "@/components/ui/table";
import { Search } from "lucide-react";
import type { StudentReportItem } from "@/types/api";
import {
  type SortField,
  type SortDir,
  type FilterMode,
  type StudentSubset,
  filterStudents,
  sortStudents,
  isSelectableStudent,
  countStudents,
} from "@/lib/overdue-students";
import { OverdueFilterBar } from "./overdue-filter-bar";
import { OverdueTableHeader } from "./overdue-table-header";
import { OverdueStudentRow } from "./overdue-student-row";

interface OverdueStudentTableProps {
  students: StudentReportItem[];
  selectedUserIds: Set<number>;
  onSelectedChange: (ids: Set<number>) => void;
  dueProcessMap?: Map<number, string>;
  novedadIds?: Set<number>;
  onRemoveNovedad?: (userId: number) => void;
  /** Filtros controlados por la página: los chips de alerta los cambian. */
  filterMode: FilterMode;
  onFilterModeChange: (mode: FilterMode) => void;
  subset: StudentSubset;
  onSubsetChange: (subset: StudentSubset) => void;
  /** Evidencias del reporte, para "deben más de la mitad". */
  selectedEvidenceCount: number;
}

const NO_NOVEDADES = new Set<number>();

export function OverdueStudentTable({
  students,
  selectedUserIds,
  onSelectedChange,
  dueProcessMap,
  novedadIds = NO_NOVEDADES,
  onRemoveNovedad,
  filterMode,
  onFilterModeChange,
  subset,
  onSubsetChange,
  selectedEvidenceCount,
}: OverdueStudentTableProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [sortField, setSortField] = useState<SortField>("overdue_count");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [searchQuery, setSearchQuery] = useState("");

  const toggleExpand = (userId: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const toggleUser = (userId: number) => {
    const next = new Set(selectedUserIds);
    if (next.has(userId)) next.delete(userId);
    else next.add(userId);
    onSelectedChange(next);
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir(field === "full_name" || field === "document" ? "asc" : "desc");
    }
  };

  // Filter + sort students
  const filteredStudents = useMemo(
    () =>
      sortStudents(
        filterStudents(students, searchQuery, filterMode, novedadIds, subset, selectedEvidenceCount),
        sortField,
        sortDir,
      ),
    [students, searchQuery, filterMode, subset, selectedEvidenceCount, sortField, sortDir, novedadIds],
  );

  // Select all: only active students with overdue, no novedades, no suspended
  const selectableStudents = useMemo(
    () => filteredStudents.filter((s) => isSelectableStudent(s, novedadIds)),
    [filteredStudents, novedadIds],
  );

  const toggleAll = () => {
    if (selectedUserIds.size === selectableStudents.length && selectableStudents.length > 0) {
      onSelectedChange(new Set());
    } else {
      onSelectedChange(new Set(selectableStudents.map((s) => s.user_id)));
    }
  };

  // Counts
  const counts = useMemo(
    () => countStudents(students, novedadIds, selectedEvidenceCount),
    [students, novedadIds, selectedEvidenceCount],
  );

  return (
    <div className="space-y-3">
      {/* Toolbar: search + filters */}
      <OverdueFilterBar
        totalCount={students.length}
        counts={counts}
        filterMode={filterMode}
        onFilterModeChange={onFilterModeChange}
        subset={subset}
        onSubsetChange={onSubsetChange}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
      />

      {/* Results count */}
      <div className="flex items-center justify-between text-xs tabular-nums text-muted-foreground">
        <span>
          {filteredStudents.length} {filteredStudents.length === 1 ? "aprendiz" : "aprendices"}
          {searchQuery.trim() ? (filteredStudents.length === 1 ? " encontrado" : " encontrados") : ""}
        </span>
        {selectableStudents.length > 0 && (
          <span>
            {selectedUserIds.size} {selectedUserIds.size === 1 ? "seleccionado" : "seleccionados"}
          </span>
        )}
      </div>

      {/* Table */}
      {filteredStudents.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-card shadow-card py-12 text-center">
          <Search
            aria-hidden="true"
            className="mb-2 h-8 w-8 text-muted-foreground/30"
          />
          <p className="text-sm text-muted-foreground">
            No se encontraron aprendices
          </p>
        </div>
      ) : (
        <div className="rounded-xl border bg-card shadow-card">
          <Table>
            <OverdueTableHeader
              sortField={sortField}
              sortDir={sortDir}
              onSort={handleSort}
              allSelected={
                selectedUserIds.size === selectableStudents.length &&
                selectableStudents.length > 0
              }
              onToggleAll={toggleAll}
            />
            <TableBody>
              {filteredStudents.map((student) => (
                <OverdueStudentRow
                  key={student.user_id}
                  student={student}
                  isExpanded={expanded.has(student.user_id)}
                  isSelected={selectedUserIds.has(student.user_id)}
                  hasNovedad={novedadIds.has(student.user_id)}
                  dueProcessStage={
                    dueProcessMap?.get(student.user_id) ?? "sin_proceso"
                  }
                  onToggleExpand={toggleExpand}
                  onToggleSelect={toggleUser}
                  onRemoveNovedad={onRemoveNovedad}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
