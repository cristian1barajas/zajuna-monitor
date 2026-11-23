"use client";

/**
 * Conectar cuenta Zajuna — credenciales de scraping del instructor.
 *
 * Las credenciales se validan EN VIVO contra Zajuna en el backend y se
 * guardan cifradas; el sincronizador trabaja con ellas en nombre del
 * instructor. Nunca se muestran de vuelta (solo documento enmascarado).
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { Topbar } from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { FloatingInput, FloatingSelect } from "@/components/ui/floating-field";
import { FolderPlus, KeyRound, ShieldCheck, Unplug, RefreshCw } from "lucide-react";
import {
  fetchZajunaAccount,
  connectZajunaAccount,
  disconnectZajunaAccount,
  type ZajunaAccountStatus,
} from "@/lib/api";

export default function ZajunaAccountPage() {
  const [account, setAccount] = useState<ZajunaAccountStatus | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [typeDocument, setTypeDocument] = useState("CC");
  const [document, setDocument] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchZajunaAccount()
      .then((acc) => {
        setAccount(acc);
        // Abre el formulario también si Zajuna rechazó las credenciales guardadas.
        setShowForm(!acc.connected || acc.status !== "ok");
      })
      .catch(() => setError("No fue posible consultar el estado de la cuenta"));
  }, []);

  const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);
    try {
      const acc = await connectZajunaAccount({
        type_document: typeDocument,
        document,
        password,
      });
      setAccount(acc);
      setShowForm(false);
      setPassword("");
      setSuccess("Cuenta Zajuna conectada y validada correctamente.");
    } catch (err) {
      setError(
        err instanceof Error && err.message.includes("400")
          ? "Zajuna rechazó las credenciales. Verifica tu documento y contraseña."
          : "No fue posible validar contra Zajuna. Intenta de nuevo en unos minutos."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm("¿Desconectar tu cuenta Zajuna? El sincronizador dejará de trabajar con tus credenciales.")) return;
    setError(null);
    setSuccess(null);
    const acc = await disconnectZajunaAccount();
    setAccount(acc);
    setShowForm(true);
  };

  return (
    <>
      <Topbar
        title="Cuenta Zajuna"
        description="El sincronizador usa tu cuenta de Zajuna para leer las calificaciones de tus fichas. Conéctala una sola vez y actualízala si cambias tu contraseña."
      />
      {/* Alineado con el encabezado, sin centrar */}
      <div className="max-w-2xl space-y-5 p-4 sm:p-6">

        {error && (
          <div role="alert" className="rounded-xl border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium leading-snug text-danger-fg">
            {error}
          </div>
        )}
        {success && (
          <div role="status" className="rounded-xl border border-ok-border bg-ok-soft px-4 py-3 text-sm font-medium leading-snug text-ok-fg">
            {success}
          </div>
        )}

        {/* Estado actual: perfil con banner teal (estilo SI Contratista) */}
        {account?.connected && (
          <section className="overflow-hidden rounded-xl border bg-card shadow-card">
            <div aria-hidden="true" className="h-12 bg-gradient-to-r from-sena-teal-deep via-sena-teal to-sena-teal-light" />
            <div className="flex flex-col gap-4 px-5 pb-5 sm:flex-row sm:items-end sm:justify-between">
              <div className="flex items-end gap-4">
                <span
                  aria-hidden="true"
                  className={`-mt-9 flex h-[4.5rem] w-[4.5rem] shrink-0 items-center justify-center rounded-full border-4 border-card text-white shadow-card ${account.status === "ok" ? "bg-active-pill" : "bg-caution"}`}
                >
                  <ShieldCheck className="h-8 w-8" />
                </span>
                <div className="min-w-0 pb-0.5">
                  <p className="text-base font-bold uppercase tracking-tight text-foreground">
                    {account.type_document}{" "}
                    <span className="font-mono tabular-nums">{account.document_masked}</span>
                  </p>
                  <span
                    className={`mt-1 inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
                      account.status === "ok"
                        ? "border-ok-border bg-ok-soft text-ok-fg"
                        : "border-warn-border bg-warn-soft text-warn-fg"
                    }`}
                  >
                    {account.status === "ok" ? "Conectada" : "Credenciales vencidas"}
                  </span>
                </div>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button variant="outline" size="sm" pill onClick={() => { setShowForm(true); setSuccess(null); }}>
                  <RefreshCw aria-hidden="true" />
                  Actualizar
                </Button>
                <Button variant="danger" size="sm" pill onClick={handleDisconnect}>
                  <Unplug aria-hidden="true" />
                  Desconectar
                </Button>
              </div>
            </div>
            <div className="border-t px-5 py-4">
              <p className="text-sm leading-relaxed text-muted-foreground">
                {account.status === "ok"
                  ? "Credenciales válidas — el sincronizador trabaja con esta cuenta."
                  : "Zajuna rechazó estas credenciales en la última sincronización. Actualízalas."}
              </p>
              {account.last_validated_at && (
                <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                  Última validación:{" "}
                  {new Date(account.last_validated_at).toLocaleString("es-CO")}
                </p>
              )}
              {account.status === "ok" && (
                <Link
                  href="/agregar-grupo"
                  className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-sena-green-dark underline-offset-2 hover:underline dark:text-sena-green"
                >
                  <FolderPlus aria-hidden="true" className="h-4 w-4" />
                  Elegir los grupos que monitoreas
                </Link>
              )}
            </div>
          </section>
        )}

        {/* Formulario de conexión / actualización */}
        {showForm && (
          <section className="overflow-hidden rounded-xl border bg-card shadow-card">
            <div className="flex items-center gap-2.5 border-b px-4 py-3">
              <KeyRound
                aria-hidden="true"
                className="h-4 w-4 shrink-0 text-sena-green-dark dark:text-sena-green"
              />
              <div>
                <h3 className="text-sm font-semibold text-foreground">
                  {account?.connected ? "Actualizar credenciales" : "Conectar tu cuenta Zajuna"}
                </h3>
              </div>
            </div>
            <div className="px-4 py-4 sm:px-5">
              <p className="mb-4 text-sm text-muted-foreground">
                Las mismas con las que entras a zajuna.sena.edu.co
              </p>
              <form onSubmit={handleSubmit} noValidate>
                <div className="mb-5 grid grid-cols-[110px_1fr] gap-3">
                  <FloatingSelect
                    id="tipo"
                    label="Tipo"
                    value={typeDocument}
                    onChange={(e) => setTypeDocument(e.target.value)}
                  >
                    <option value="CC">CC</option>
                    <option value="CE">CE</option>
                    <option value="TI">TI</option>
                    <option value="PEP">PEP</option>
                  </FloatingSelect>
                  <FloatingInput
                    id="documento"
                    label="Número de documento"
                    type="text"
                    inputMode="numeric"
                    placeholder="1234567890"
                    required
                    value={document}
                    onChange={(e) => { setDocument(e.target.value); setError(null); }}
                  />
                </div>

                <div className="mb-6">
                  <FloatingInput
                    id="zj-password"
                    label="Contraseña de Zajuna"
                    type="password"
                    placeholder="••••••••"
                    autoComplete="off"
                    required
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setError(null); }}
                  />
                </div>

                <Button type="submit" size="lg" pill disabled={isSubmitting} className="w-full">
                  {isSubmitting
                    ? "Validando contra Zajuna (toma unos segundos)…"
                    : "Validar y conectar"}
                </Button>

                {account?.connected && (
                  <Button
                    variant="ghost"
                    pill
                    onClick={() => { setShowForm(false); setError(null); }}
                    className="mt-2 w-full"
                  >
                    Cancelar
                  </Button>
                )}
              </form>
            </div>
          </section>
        )}

        {/* Nota de seguridad */}
        <div role="note" className="rounded-xl border bg-card shadow-card px-4 py-3 text-xs leading-relaxed text-muted-foreground">
          <strong className="font-semibold text-foreground">¿Cómo se guardan?</strong>{" "}
          Tus credenciales se validan directamente contra Zajuna y se almacenan
          cifradas en el servidor del monitor. Solo el sincronizador las usa —
          nunca se muestran de vuelta ni se comparten con otras aplicaciones. Si
          cambias tu contraseña en Zajuna, vuelve aquí y actualízala.
        </div>
      </div>
    </>
  );
}
