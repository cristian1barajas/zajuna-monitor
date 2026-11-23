"use client";

import { useCallback, useEffect, useState } from "react";
import { downloadActa, fetchActas } from "@/lib/api";
import type {
  ActaRequest,
  ActasResponse,
  FechaActa,
  SoporteRegistro,
} from "@/types/api";
import { ActaDialog } from "./acta-dialog";
import { ActasSection } from "./actas-section";
import { saveFile } from "./save-file";

interface ActasPanelProps {
  ficha: string;
  /** Cambia cuando se descarga un ZIP: hay soportes nuevos en el registro. */
  refreshKey: number;
  onSoportes: (soportes: SoporteRegistro[]) => void;
}

/** Actas del equipo ejecutor: lista por día de envío y diálogo para generar el Word. */
export function ActasPanel({ ficha, refreshKey, onSoportes }: ActasPanelProps) {
  const [data, setData] = useState<ActasResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [open, setOpen] = useState<FechaActa | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchActas(ficha)
      .then((res) => {
        setData(res);
        onSoportes(res.soportes);
      })
      .catch((e: Error) => setLoadError(e.message));
  }, [ficha, onSoportes]);

  useEffect(load, [load, refreshKey]);

  const generate = async (body: ActaRequest) => {
    setGenerating(true);
    setError(null);
    try {
      const { blob, filename } = await downloadActa(ficha, body);
      saveFile(blob, filename);
      setOpen(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  if (loadError) {
    return (
      <p className="rounded-lg border border-danger-border bg-danger-soft p-3 text-sm text-danger-fg">
        No se pudieron cargar las actas: {loadError}
      </p>
    );
  }
  if (!data) return null;

  return (
    <>
      <ActasSection
        fechas={data.fechas}
        onGenerate={(f) => {
          setError(null);
          setOpen(f);
        }}
      />
      <ActaDialog
        fecha={open}
        siguienteNumero={data.siguiente_numero}
        asistentes={data.asistentes}
        horaInicio={data.hora_inicio}
        horaFin={data.hora_fin}
        generating={generating}
        error={error}
        onClose={() => setOpen(null)}
        onGenerate={generate}
      />
    </>
  );
}
