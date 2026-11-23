"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useParams } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { CronogramaUploader } from "@/components/cronograma/cronograma-uploader";
import { CronogramaTable, type CronogramaChange } from "@/components/cronograma/cronograma-table";
import { CronogramaTimeline } from "@/components/cronograma/cronograma-timeline";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fetchCronograma, postCronograma, deleteCronograma, fetchFichaDetail, fetchHealth } from "@/lib/api";
import { FileText, Save, Trash2 } from "lucide-react";
import type { CronogramaEntry, CronogramaPdfPreview, EvidenceItem } from "@/types/api";

const CODE_RE = /GA\d+-\d{9}-AA\d+-EV\d+/;

/** Clave de una evidencia: su código si lo trae, si no el nombre completo. */
const keyOf = (name: string) => name.replace(/\s/g, "").match(CODE_RE)?.[0] ?? name.trim();

interface PdfNotice {
  files: CronogramaPdfPreview["files"];
  added: number;
  changed: number;
  same: number;
  warnings: string[];
}

export default function CronogramaPage() {
  const params = useParams();
  const ficha = params.ficha as string;

  const [entries, setEntries] = useState<CronogramaEntry[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [lastScrape, setLastScrape] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasUnsaved, setHasUnsaved] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [changes, setChanges] = useState<Map<string, CronogramaChange>>(new Map());
  const [pdfNotice, setPdfNotice] = useState<PdfNotice | null>(null);
  // La línea de tiempo es la vista de consulta; la tabla, la de edición
  const [view, setView] = useState<"timeline" | "table">("timeline");
  const [evidences, setEvidences] = useState<EvidenceItem[]>([]);

  const clearPreview = () => {
    setChanges(new Map());
    setPdfNotice(null);
  };

  const loadData = useCallback(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      fetchCronograma(ficha).catch(() => null),
      fetchHealth(),
      fetchFichaDetail(ficha).catch(() => null),
    ])
      .then(([crono, health, detail]) => {
        if (crono) {
          setEntries(crono.entries);
          setUpdatedAt(crono.updated_at);
        }
        setLastScrape(health.last_scrape);
        setEvidences(detail?.evidences ?? []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [ficha]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- TODO(code-quality): loadData hace setLoading síncrono al iniciar el fetch en el montaje; mover a un data-fetching hook implicaría cambio de comportamiento
    loadData();
  }, [loadData]);

  const handleParsed = (parsed: { evidence_name: string; cutoff_date: string }[]) => {
    const newEntries: CronogramaEntry[] = parsed.map((p) => ({
      evidence_name: p.evidence_name,
      evidence_item_id: null,
      cutoff_date: p.cutoff_date,
    }));
    setEntries(newEntries);
    setHasUnsaved(true);
    clearPreview();
    setView("table");
  };

  // Los PDF se suman: cada evidencia queda con la fecha que trae el PDF
  const handlePdfPreview = (preview: CronogramaPdfPreview) => {
    setError(null);
    const merged = [...entries];
    const position = new Map(merged.map((e, i) => [keyOf(e.evidence_name), i]));
    const nextChanges = new Map(changes);
    let added = 0;
    let changed = 0;
    let same = 0;

    for (const incoming of preview.entries) {
      const at = position.get(keyOf(incoming.evidence_name));
      if (at === undefined) {
        position.set(keyOf(incoming.evidence_name), merged.length);
        merged.push(incoming);
        nextChanges.set(incoming.evidence_name, { kind: "new" });
        added++;
      } else if (merged[at].cutoff_date !== incoming.cutoff_date) {
        const previous = merged[at];
        merged[at] = { ...incoming, evidence_item_id: incoming.evidence_item_id ?? previous.evidence_item_id };
        const earlier = changes.get(previous.evidence_name);
        nextChanges.delete(previous.evidence_name);
        nextChanges.set(
          incoming.evidence_name,
          earlier?.kind === "new" ? earlier : { kind: "date", previous: earlier?.kind === "date" ? earlier.previous : previous.cutoff_date },
        );
        changed++;
      } else {
        same++;
      }
    }

    setEntries(merged);
    setChanges(nextChanges);
    setPdfNotice({ files: preview.files, added, changed, same, warnings: preview.warnings });
    // Las marcas Nueva / Cambia fecha viven en la tabla
    setView("table");
    if (added + changed > 0) setHasUnsaved(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const result = await postCronograma(
        ficha,
        entries.map((e) => ({
          evidence_name: e.evidence_name,
          cutoff_date: e.cutoff_date,
        })),
      );
      setEntries(result.entries);
      setUpdatedAt(result.updated_at);
      setHasUnsaved(false);
      clearPreview();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setError(null);
    setConfirmDelete(false);
    try {
      await deleteCronograma(ficha);
      setEntries([]);
      setUpdatedAt(null);
      setHasUnsaved(false);
      clearPreview();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al eliminar");
    }
  };

  const handleRemoveEntry = (index: number) => {
    setEntries((prev) => prev.filter((_, i) => i !== index));
    setHasUnsaved(true);
  };

  // Vuelve a lo guardado en el servidor (o a vacío si nunca se guardó).
  const handleDiscard = () => {
    setEntries([]);
    setUpdatedAt(null);
    setHasUnsaved(false);
    clearPreview();
    loadData();
  };

  if (loading) {
    return (
      <>
        <Topbar title="Cronograma" />
        <div className="space-y-4 p-6">
          <Skeleton className="h-40 rounded-lg" />
          <Skeleton className="h-96 rounded-lg" />
        </div>
      </>
    );
  }

  const hasEntries = entries.length > 0;

  return (
    <>
      <Topbar
        title="Cronograma"
        lastScrape={lastScrape}
        description="Fechas de cierre de las evidencias. Alimentan el filtro de cierre de Por calificar y los reportes. Los PDF de cada mes se suman; un CSV reemplaza todo."
        actions={
          hasEntries && (
            <CronogramaUploader
              variant="button"
              ficha={ficha}
              onParsed={handleParsed}
              onPdfPreview={handlePdfPreview}
              onError={setError}
            />
          )
        }
      />
      <div className="space-y-5 p-6">
        {hasUnsaved && (
          <div
            role="status"
            className="sticky top-14 z-20 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warn-border bg-warn-soft px-4 py-2.5 shadow-card"
          >
            <p className="text-sm font-medium text-warn-fg">
              {hasEntries
                ? "Cambios sin guardar. Los cierres no se aplican hasta que guardes."
                : "Quitaste todas las filas. Descarta los cambios para volver a lo guardado."}
            </p>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" pill onClick={handleDiscard} disabled={saving}>
                Descartar
              </Button>
              {hasEntries && (
                <Button size="sm" pill onClick={handleSave} disabled={saving}>
                  <Save aria-hidden="true" />
                  {saving ? "Guardando..." : "Guardar"}
                </Button>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-danger-border bg-danger-soft p-4 text-sm text-danger-fg">
            {error}
          </div>
        )}

        {pdfNotice && (
          <section role="status" className="rounded-xl border bg-card px-4 py-3 shadow-card">
            <div className="flex items-start gap-3">
              <FileText aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="space-y-1 text-sm">
                <p className="font-medium text-foreground">
                  {pdfNotice.files.length === 1 ? "1 PDF leído" : `${pdfNotice.files.length} PDF leídos`}:{" "}
                  <span className="tabular-nums">
                    {pdfNotice.added} {pdfNotice.added === 1 ? "evidencia nueva" : "evidencias nuevas"} ·{" "}
                    {pdfNotice.changed} con fecha cambiada · {pdfNotice.same} sin cambios
                  </span>
                </p>
                <p className="text-xs text-muted-foreground">
                  {pdfNotice.added + pdfNotice.changed > 0
                    ? "Revisa las filas marcadas y pulsa Guardar para aplicarlas."
                    : "El cronograma ya tenía estas fechas; no hay nada que guardar."}
                </p>
                {pdfNotice.warnings.length > 0 && (
                  <ul className="list-disc space-y-0.5 pl-4 text-xs text-warn-fg">
                    {pdfNotice.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </section>
        )}

        {hasEntries ? (
          <Tabs value={view} onValueChange={(v) => setView(v as "timeline" | "table")}>
            <TabsList>
              <TabsTrigger value="timeline">Línea de tiempo</TabsTrigger>
              <TabsTrigger value="table">Tabla</TabsTrigger>
            </TabsList>

            <TabsContent value="timeline" className="mt-4">
              <CronogramaTimeline ficha={ficha} entries={entries} evidences={evidences} />
            </TabsContent>

            <TabsContent value="table" className="mt-4">
              <section className="overflow-hidden rounded-xl border bg-card shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
                  <h2 className="text-sm font-semibold text-foreground">
                    Cronograma{" "}
                    <span className="font-normal tabular-nums text-muted-foreground">
                      {entries.length} evidencias
                    </span>
                  </h2>
                  {updatedAt && (
                    <span className="text-xs tabular-nums text-muted-foreground">
                      Actualizado: {new Date(updatedAt).toLocaleDateString("es-CO")}
                    </span>
                  )}
                </div>
                <CronogramaTable
                  entries={entries}
                  editable={true}
                  onRemoveEntry={handleRemoveEntry}
                  unsaved={hasUnsaved}
                  changes={changes}
                />
                {updatedAt && (
                  <div className="flex justify-end border-t px-4 py-2.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-danger-fg hover:bg-danger-soft hover:text-danger-fg"
                      onClick={() => setConfirmDelete(true)}
                    >
                      <Trash2 aria-hidden="true" />
                      Eliminar cronograma
                    </Button>
                  </div>
                )}
              </section>
            </TabsContent>
          </Tabs>
        ) : (
          <section className="rounded-xl border bg-card p-4 shadow-card">
            <CronogramaUploader ficha={ficha} onParsed={handleParsed} onPdfPreview={handlePdfPreview} />
          </section>
        )}
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent
          title="Eliminar cronograma"
          subtitle="Se borran las fechas de cierre de esta ficha. Por calificar y los reportes dejan de usarlas hasta que subas otro archivo."
          className="max-w-md"
          footer={
            <>
              <Button variant="outline" onClick={() => setConfirmDelete(false)}>
                Cancelar
              </Button>
              <Button variant="danger" onClick={handleDelete}>
                <Trash2 aria-hidden="true" />
                Eliminar cronograma
              </Button>
            </>
          }
        />

      </Dialog>
    </>
  );
}
