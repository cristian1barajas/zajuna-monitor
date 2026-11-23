"use client";

import { useState } from "react";
import { Check, Copy, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { downloadEmailDraftsEml } from "@/lib/api";
import type { EmailDraft } from "@/types/api";
import { StageBadge } from "@/components/due-process/stage-badge";

interface EmailPreviewModalProps {
  ficha: string;
  open: boolean;
  onClose: () => void;
  drafts: EmailDraft[];
  onConfirm: () => void;
  confirming: boolean;
}

/** Entrega el archivo al navegador con `<a download>`. */
function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function EmailPreviewModal({
  ficha,
  open,
  onClose,
  drafts,
  onConfirm,
  confirming,
}: EmailPreviewModalProps) {
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [copiedAll, setCopiedAll] = useState(false);
  // "all" = zip con todos; número = .eml de ese aprendiz
  const [downloading, setDownloading] = useState<number | "all" | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const formatSingleDraft = (d: EmailDraft) =>
    `Para: ${d.email}\nAsunto: ${d.subject}\n\n${d.body}`;

  const handleCopyOne = async (draft: EmailDraft) => {
    await navigator.clipboard.writeText(formatSingleDraft(draft));
    setCopiedId(draft.user_id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleCopyAll = async () => {
    const text = drafts.map(formatSingleDraft).join("\n\n---\n\n");
    await navigator.clipboard.writeText(text);
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  const handleDownload = async (target: EmailDraft | "all") => {
    setDownloading(target === "all" ? "all" : target.user_id);
    setDownloadError(null);
    try {
      const { blob, filename } =
        target === "all"
          ? await downloadEmailDraftsEml(ficha, drafts, true)
          : await downloadEmailDraftsEml(ficha, [target]);
      saveFile(blob, filename);
    } catch (e) {
      setDownloadError(
        e instanceof Error ? e.message : "No se pudieron descargar los correos",
      );
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent
        title="Correos generados"
        subtitle={`${drafts.length} ${drafts.length === 1 ? "borrador listo" : "borradores listos"} para copiar o descargar y enviar`}
        footer={
          <>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" pill onClick={handleCopyAll}>
                {copiedAll ? (
                  <>
                    <Check aria-hidden="true" className="text-ok-fg" />
                    Todos copiados
                  </>
                ) : (
                  <>
                    <Copy aria-hidden="true" />
                    Copiar todos
                  </>
                )}
              </Button>
              <Button
                variant="outline"
                pill
                onClick={() => handleDownload("all")}
                disabled={downloading !== null || drafts.length === 0}
              >
                {downloading === "all" ? (
                  <Loader2 aria-hidden="true" className="animate-spin" />
                ) : (
                  <Download aria-hidden="true" />
                )}
                Descargar todos (.zip)
              </Button>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" pill onClick={onClose}>
                Cerrar
              </Button>
              <Button pill onClick={onConfirm} disabled={confirming}>
                {confirming ? (
                  <Loader2 aria-hidden="true" className="animate-spin" />
                ) : (
                  <Check aria-hidden="true" />
                )}
                Confirmar y registrar
              </Button>
            </div>
          </>
        }
      >
        <div className="border-b px-6 py-3 text-xs text-muted-foreground">
          Doble clic abre el borrador en Outlook; en el Outlook nuevo, arrástralo
          al panel de lectura.
          {downloadError && (
            <p role="alert" className="mt-2 text-danger-fg">
              {downloadError}
            </p>
          )}
        </div>

        {/* Body: borradores separados por 1px */}
        <div className="divide-y">
          {drafts.map((draft) => (
            <div key={draft.user_id} className="px-6 py-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="font-medium text-foreground">
                    {draft.full_name}
                  </span>
                  <span className="font-mono text-sm tabular-nums text-muted-foreground">
                    {draft.document}
                  </span>
                  <StageBadge stage={draft.stage} />
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button variant="outline" size="sm" pill onClick={() => handleCopyOne(draft)}>
                    {copiedId === draft.user_id ? (
                      <>
                        <Check aria-hidden="true" className="h-3 w-3 text-ok-fg" />
                        Copiado
                      </>
                    ) : (
                      <>
                        <Copy aria-hidden="true" className="h-3 w-3" />
                        Copiar
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    pill
                    onClick={() => handleDownload(draft)}
                    disabled={downloading !== null}
                    aria-label={`Descargar .eml de ${draft.full_name}`}
                  >
                    {downloading === draft.user_id ? (
                      <Loader2 aria-hidden="true" className="h-3 w-3 animate-spin" />
                    ) : (
                      <Download aria-hidden="true" className="h-3 w-3" />
                    )}
                    Descargar .eml
                  </Button>
                </div>
              </div>

              <div className="mb-2 text-sm text-muted-foreground">
                Para: {draft.email || "sin correo registrado"}
              </div>

              <div className="mb-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm font-medium text-foreground">
                {draft.subject}
              </div>

              <textarea
                readOnly
                value={draft.body}
                rows={8}
                aria-label={`Cuerpo del correo para ${draft.full_name}`}
                className="w-full resize-none rounded-xl border bg-muted/20 p-3 font-mono text-xs leading-relaxed text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out focus:border-sena-green focus:ring-2 focus:ring-ring/30"
              />
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
