"use client";

/**
 * Aviso en el dashboard sobre el estado de la cuenta Zajuna:
 * - Sin conectar → invita a conectarla (el sincronizador la necesita).
 * - Credenciales inválidas → pide actualizarlas.
 * No renderiza nada si la cuenta está conectada y válida.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { KeyRound } from "lucide-react";
import { fetchZajunaAccount, type ZajunaAccountStatus } from "@/lib/api";

export function ZajunaAccountBanner() {
  const [account, setAccount] = useState<ZajunaAccountStatus | null>(null);

  useEffect(() => {
    fetchZajunaAccount()
      .then(setAccount)
      .catch(() => {});
  }, []);

  if (!account || (account.connected && account.status === "ok")) return null;

  const invalid = account.connected && account.status !== "ok";

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 ${
        invalid
          ? "border-danger-border bg-danger-soft"
          : "border-warn-border bg-warn-soft"
      }`}
    >
      <div className="flex items-center gap-3">
        <KeyRound
          className={`h-4 w-4 shrink-0 ${invalid ? "text-danger-fg" : "text-warn-fg"}`}
        />
        <p className={`text-sm font-medium ${invalid ? "text-danger-fg" : "text-warn-fg"}`}>
          {invalid
            ? "Zajuna rechazó tus credenciales — actualízalas para que la sincronización siga funcionando."
            : "Conecta tu cuenta Zajuna para que el sincronizador trabaje con tus fichas."}
        </p>
      </div>
      <Link
        href="/cuenta-zajuna"
        className="shrink-0 rounded-md bg-sena-green px-3 py-1.5 text-xs font-semibold text-white transition-colors duration-150 ease-out hover:bg-sena-green-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 dark:text-background dark:hover:bg-sena-green-light"
      >
        {invalid ? "Actualizar credenciales" : "Conectar cuenta"}
      </Link>
    </div>
  );
}
