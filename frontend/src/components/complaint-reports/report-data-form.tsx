"use client";

import { useCallback, useEffect, useState } from "react";
import { Calendar, CheckCircle2, ImageIcon, Loader2, Phone, UserRound, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  deleteParticipantScreenshot,
  importPhoneData,
  uploadParticipantScreenshot,
} from "@/lib/api";

/** Carpeta con los Excel de teléfonos; se recuerda en este navegador. */
const PHONES_DIR_KEY = "zajuna_phones_dir";
const DEFAULT_PHONES_DIR = "C:\\Users\\crist\\Downloads\\Datos";

const INPUT_CLASS =
  "h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out focus:border-sena-green focus:ring-2 focus:ring-ring/30";

function readPhonesDir(): string {
  try {
    return localStorage.getItem(PHONES_DIR_KEY) || DEFAULT_PHONES_DIR;
  } catch {
    return DEFAULT_PHONES_DIR;
  }
}

interface ReportDataFormProps {
  ficha: string;
  coordinatorName: string;
  onCoordinatorChange: (name: string) => void;
  reportDate: string;
  onReportDateChange: (date: string) => void;
  onError: (message: string | null) => void;
}

/** Paso 3 de Informes de queja: datos que van en los documentos Word. */
export function ReportDataForm({
  ficha,
  coordinatorName,
  onCoordinatorChange,
  reportDate,
  onReportDateChange,
  onError,
}: ReportDataFormProps) {
  const [phonesDir, setPhonesDir] = useState(readPhonesDir);
  const [phoneImported, setPhoneImported] = useState(false);
  const [importingPhones, setImportingPhones] = useState(false);
  const [screenshotFile, setScreenshotFile] = useState<File | null>(null);
  const [uploadingScreenshot, setUploadingScreenshot] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(PHONES_DIR_KEY, phonesDir);
    } catch {
      /* sin almacenamiento local: la ruta vive solo en esta visita */
    }
  }, [phonesDir]);

  const handleImportPhones = async () => {
    setImportingPhones(true);
    onError(null);
    try {
      await importPhoneData(phonesDir);
      setPhoneImported(true);
    } catch (e) {
      onError(e instanceof Error ? e.message : "No se pudieron importar los teléfonos");
    } finally {
      setImportingPhones(false);
    }
  };

  const handleScreenshotUpload = useCallback(
    async (file: File) => {
      setScreenshotFile(file);
      setUploadingScreenshot(true);
      onError(null);
      try {
        await uploadParticipantScreenshot(ficha, file);
      } catch (e) {
        onError(e instanceof Error ? e.message : "No se pudo subir la captura");
        setScreenshotFile(null);
      } finally {
        setUploadingScreenshot(false);
      }
    },
    [ficha, onError],
  );

  const handleRemoveScreenshot = async () => {
    await deleteParticipantScreenshot(ficha);
    setScreenshotFile(null);
  };

  return (
    <div className="divide-y">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <UserRound aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
        <label htmlFor="nombre-coordinador" className="min-w-0 flex-1 text-sm font-medium text-foreground">
          Coordinador que recibe el informe
        </label>
        <input
          id="nombre-coordinador"
          type="text"
          value={coordinatorName}
          onChange={(e) => onCoordinatorChange(e.target.value)}
          className={`${INPUT_CLASS} w-full sm:w-80`}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <Calendar aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
        <label htmlFor="fecha-informe" className="min-w-0 flex-1 text-sm font-medium text-foreground">
          Fecha del informe
        </label>
        <input
          id="fecha-informe"
          type="date"
          value={reportDate}
          onChange={(e) => onReportDateChange(e.target.value)}
          className={`${INPUT_CLASS} tabular-nums`}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <Phone aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1 text-sm">
          <p className="font-medium text-foreground">Teléfonos de contacto</p>
          <p className={phoneImported ? "text-xs text-ok-fg" : "text-xs text-muted-foreground"}>
            {phoneImported ? "Teléfonos importados" : "Carpeta con los Excel de datos de los aprendices"}
          </p>
        </div>
        <input
          aria-label="Carpeta de los Excel de teléfonos"
          type="text"
          value={phonesDir}
          onChange={(e) => {
            setPhonesDir(e.target.value);
            setPhoneImported(false);
          }}
          className={`${INPUT_CLASS} w-full font-mono text-xs sm:w-72`}
        />
        {phoneImported ? (
          <CheckCircle2 aria-hidden="true" className="h-4 w-4 shrink-0 text-ok-fg" />
        ) : (
          <Button size="sm" pill onClick={handleImportPhones} disabled={importingPhones || !phonesDir}>
            {importingPhones ? <Loader2 aria-hidden="true" className="animate-spin" /> : "Importar"}
          </Button>
        )}
      </div>

      <div
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const file = e.dataTransfer.files[0];
          if (file && file.type.startsWith("image/")) handleScreenshotUpload(file);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        className={`flex flex-wrap items-center gap-3 px-4 py-3 transition-colors duration-150 ease-out ${
          dragOver ? "bg-accent" : screenshotFile ? "bg-ok-soft/50" : ""
        }`}
      >
        <ImageIcon aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1 text-sm">
          <p className="font-medium text-foreground">Captura de participantes</p>
          <p className={screenshotFile ? "truncate text-xs text-ok-fg" : "text-xs text-muted-foreground"}>
            {screenshotFile ? screenshotFile.name : "Arrastra la imagen o elígela"}
          </p>
        </div>
        {screenshotFile ? (
          <button
            onClick={handleRemoveScreenshot}
            aria-label="Quitar captura"
            className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors duration-150 ease-out hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        ) : (
          <label className="shrink-0 cursor-pointer rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors duration-150 ease-out hover:bg-primary/90">
            {uploadingScreenshot ? <Loader2 aria-hidden="true" className="h-3.5 w-3.5 animate-spin" /> : "Elegir imagen"}
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleScreenshotUpload(f);
              }}
            />
          </label>
        )}
      </div>
    </div>
  );
}
