"use client";

import { useState } from "react";
import { FileText, Loader2, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import type { ActaAsistente, ActaRequest, FechaActa } from "@/types/api";
import { formatDay } from "./stages";

interface ActaDialogProps {
  fecha: FechaActa | null;
  siguienteNumero: number;
  asistentes: ActaAsistente[];
  horaInicio: string;
  horaFin: string;
  generating: boolean;
  error: string | null;
  onClose: () => void;
  onGenerate: (body: ActaRequest) => void;
}

const inputClass =
  "h-9 w-full rounded-lg border border-input bg-card px-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring";
const labelClass = "mb-1 block text-xs font-medium text-muted-foreground";

/** Datos que no salen del sistema: número, fecha y horas de la reunión, e instructores que firman. */
export function ActaDialog(props: ActaDialogProps) {
  const { fecha, onClose } = props;
  return (
    <Dialog open={fecha !== null} onOpenChange={(open) => !open && onClose()}>
      {/* La key reinicia el formulario con los últimos datos usados cada vez que se abre para otro día. */}
      {fecha && <ActaForm key={fecha.fecha_envio} {...props} fecha={fecha} />}
    </Dialog>
  );
}

function ActaForm({
  fecha,
  siguienteNumero,
  asistentes,
  horaInicio,
  horaFin,
  generating,
  error,
  onGenerate,
}: ActaDialogProps & { fecha: FechaActa }) {
  const [numero, setNumero] = useState(fecha.acta_numero ?? siguienteNumero);
  const [fechaActa, setFechaActa] = useState(fecha.fecha_envio);
  const [inicio, setInicio] = useState(horaInicio);
  const [fin, setFin] = useState(horaFin);
  const [personas, setPersonas] = useState<ActaAsistente[]>(
    asistentes.length ? asistentes : [{ nombre: "", dependencia: "SENA/CMM" }]
  );

  const firmantes = personas.filter((p) => p.nombre.trim());
  const valid =
    numero > 0 && fechaActa && inicio.trim() && fin.trim() && firmantes.length;

  const update = (i: number, patch: Partial<ActaAsistente>) =>
    setPersonas((list) =>
      list.map((p, j) => (j === i ? { ...p, ...patch } : p))
    );

  return (
    <DialogContent
      title="Acta del equipo ejecutor"
      subtitle={`Llamados enviados el ${formatDay(fecha.fecha_envio)} · ${fecha.llamados} aprendices`}
      className="max-w-xl"
      footer={
        <>
          <p className="text-xs text-muted-foreground">
            La relación de aprendices sale de Debido proceso y de los soportes
            descargados.
          </p>
          <Button
            disabled={!valid || generating}
            onClick={() =>
              onGenerate({
                fecha_envio: fecha.fecha_envio,
                numero,
                fecha_acta: fechaActa,
                hora_inicio: inicio,
                hora_fin: fin,
                asistentes: firmantes.map((p) => ({
                  nombre: p.nombre.trim(),
                  dependencia: p.dependencia.trim() || "SENA/CMM",
                })),
              })
            }
          >
            {generating ? (
              <Loader2 aria-hidden="true" className="animate-spin" />
            ) : (
              <FileText aria-hidden="true" />
            )}
            Generar Word
          </Button>
        </>
      }
    >
      <div className="space-y-5 px-6 py-5">
        {error && (
          <div
            role="alert"
            className="rounded-lg border border-danger-border bg-danger-soft p-3 text-sm text-danger-fg"
          >
            {error}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <label htmlFor="acta-numero" className={labelClass}>
              Acta No.
            </label>
            <input
              id="acta-numero"
              type="number"
              min={1}
              value={numero}
              onChange={(e) => setNumero(Number(e.target.value))}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="acta-fecha" className={labelClass}>
              Fecha del acta
            </label>
            <input
              id="acta-fecha"
              type="date"
              value={fechaActa}
              onChange={(e) => setFechaActa(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="acta-inicio" className={labelClass}>
              Hora inicio
            </label>
            <input
              id="acta-inicio"
              value={inicio}
              onChange={(e) => setInicio(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="acta-fin" className={labelClass}>
              Hora fin
            </label>
            <input
              id="acta-fin"
              value={fin}
              onChange={(e) => setFin(e.target.value)}
              className={inputClass}
            />
          </div>
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-semibold">
            Instructores que firman
          </legend>
          <ul className="space-y-2">
            {personas.map((p, i) => (
              <li key={i} className="flex items-center gap-2">
                <input
                  aria-label={`Nombre del instructor ${i + 1}`}
                  placeholder="Nombre del instructor"
                  value={p.nombre}
                  onChange={(e) => update(i, { nombre: e.target.value })}
                  className={inputClass}
                />
                <input
                  aria-label={`Dependencia del instructor ${i + 1}`}
                  value={p.dependencia}
                  onChange={(e) => update(i, { dependencia: e.target.value })}
                  className={`${inputClass} max-w-32`}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  disabled={personas.length === 1}
                  onClick={() =>
                    setPersonas((list) => list.filter((_, j) => j !== i))
                  }
                  aria-label={`Quitar instructor ${i + 1}`}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ul>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2"
            onClick={() =>
              setPersonas((list) => [
                ...list,
                { nombre: "", dependencia: "SENA/CMM" },
              ])
            }
          >
            <Plus aria-hidden="true" /> Agregar instructor
          </Button>
          <p className="mt-1 text-xs text-muted-foreground">
            Cada uno queda en la tabla de asistentes con la firma en blanco.
          </p>
        </fieldset>
      </div>
    </DialogContent>
  );
}
