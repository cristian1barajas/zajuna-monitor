import type {
  ActaRequest,
  ActasResponse,
  BuscarLlamadosResponse,
  OutlookSessionStatus,
  ZipJobStatus,
} from "@/types/api";

import { authedFetch } from "./core";

/** Error con el `detail` de FastAPI: aquí los mensajes sí le sirven al instructor. */
async function failWithDetail(res: Response): Promise<never> {
  let detail = `API error ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    // respuesta sin JSON: se queda el código
  }
  throw new Error(detail);
}

async function sendJson<T>(
  path: string,
  method: string,
  body?: unknown
): Promise<T> {
  const res = await authedFetch(path, {
    method,
    cache: "no-store",
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) await failWithDetail(res);
  return res.json();
}

export function fetchOutlookSession() {
  return sendJson<OutlookSessionStatus>("/api/outlook/session", "GET");
}

/** Abre Chrome en el equipo donde corre la API para iniciar sesión con el correo SENA. */
export function startOutlookSession() {
  return sendJson<OutlookSessionStatus>("/api/outlook/session", "POST");
}

export function disconnectOutlookSession() {
  return sendJson<OutlookSessionStatus>("/api/outlook/session", "DELETE");
}

export function searchLlamados(
  ficha: string,
  fechas: string[],
  etapas: string[]
) {
  return sendJson<BuscarLlamadosResponse>(
    `/api/fichas/${ficha}/soportes-llamados/buscar`,
    "POST",
    { fechas, etapas }
  );
}

/** ZIP con un PDF por correo, en carpetas por etapa. */
export function startLlamadosZip(ficha: string, messageIds: string[]) {
  return sendJson<ZipJobStatus>(
    `/api/fichas/${ficha}/soportes-llamados/zip`,
    "POST",
    { message_ids: messageIds }
  );
}

export function fetchLlamadosZipStatus(ficha: string, jobId: string) {
  return sendJson<ZipJobStatus>(
    `/api/fichas/${ficha}/soportes-llamados/zip/${jobId}`,
    "GET"
  );
}

const POLL_MS = 1500;

/**
 * Imprime los correos con la opción "Imprimir" de Outlook (en el Chrome de la
 * sesión) y devuelve un ZIP por día de envío: un PDF por correo, en carpetas
 * por etapa. Unos segundos por correo; `onProgress` recibe el avance.
 */
export async function printLlamadosZips(
  ficha: string,
  messageIds: string[],
  onProgress: (job: ZipJobStatus) => void
): Promise<{ blob: Blob; filename: string }[]> {
  let job = await startLlamadosZip(ficha, messageIds);
  onProgress(job);
  while (job.status === "running") {
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    job = await fetchLlamadosZipStatus(ficha, job.job_id);
    onProgress(job);
  }
  if (job.status !== "done") {
    throw new Error(job.message || "No se pudieron imprimir los correos");
  }
  const files = [];
  for (const [i, filename] of job.archivos.entries()) {
    const res = await authedFetch(
      `/api/fichas/${ficha}/soportes-llamados/zip/${job.job_id}/archivo/${i}`
    );
    if (!res.ok) await failWithDetail(res);
    files.push({ blob: await res.blob(), filename });
  }
  return files;
}

// --- Actas del equipo ejecutor ---

export function fetchActas(ficha: string) {
  return sendJson<ActasResponse>(
    `/api/fichas/${ficha}/actas-equipo-ejecutor`,
    "GET"
  );
}

/** Acta en Word con la relación de llamados enviados ese día y firmas en blanco. */
export async function downloadActa(
  ficha: string,
  body: ActaRequest
): Promise<{ blob: Blob; filename: string }> {
  const res = await authedFetch(`/api/fichas/${ficha}/actas-equipo-ejecutor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) await failWithDetail(res);
  const match = res.headers
    .get("Content-Disposition")
    ?.match(/filename="([^"]+)"/);
  return {
    blob: await res.blob(),
    filename: match?.[1] ?? "ACTA_EQUIPO_EJECUTOR.docx",
  };
}
