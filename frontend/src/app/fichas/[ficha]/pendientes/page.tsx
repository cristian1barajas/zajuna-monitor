import { redirect } from "next/navigation";

/**
 * "Sin nota" ahora es la pestaña Evidencias del Resumen (filtros, cierre y
 * aprendices sin nota por evidencia). Se conserva la ruta para enlaces viejos.
 */
export default async function SinNotaRedirect({
  params,
}: {
  params: Promise<{ ficha: string }>;
}) {
  const { ficha } = await params;
  redirect(`/fichas/${ficha}?tab=evidencias`);
}
