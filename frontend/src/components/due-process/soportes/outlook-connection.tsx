"use client";

import { Loader2, LogIn, Mail, Unplug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { OutlookSessionStatus } from "@/types/api";

interface OutlookConnectionProps {
  session: OutlookSessionStatus | null;
  busy: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Franja de conexión con el correo SENA. La API abre Chrome en este equipo;
 * el instructor inicia sesión ahí y la ventana queda minimizada para imprimir.
 */
export function OutlookConnection({
  session,
  busy,
  onConnect,
  onDisconnect,
}: OutlookConnectionProps) {
  const status = session?.status ?? "idle";
  const connected = status === "connected";
  const waiting = status === "waiting_login";

  return (
    <section
      aria-label="Conexión con el correo SENA"
      className="flex flex-col gap-3 rounded-xl border bg-card px-4 py-3 shadow-card sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex min-w-0 items-center gap-3" aria-live="polite">
        <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-sena-green-dark dark:text-sena-green">
          <Mail aria-hidden="true" className="h-4 w-4" />
          <span
            aria-hidden="true"
            className={cn(
              "absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-card",
              connected
                ? "bg-ok"
                : waiting
                  ? "animate-pulse bg-warn"
                  : status === "error"
                    ? "bg-danger"
                    : "bg-muted-foreground/40"
            )}
          />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold">
            {connected
              ? session?.account
              : waiting
                ? "Esperando que inicies sesión…"
                : "Correo SENA sin conectar"}
          </p>
          <p
            className={cn(
              "truncate text-xs",
              status === "error" ? "text-danger-fg" : "text-muted-foreground"
            )}
          >
            {connected
              ? `Outlook conectado${session?.expires_at ? ` · vence ${formatTime(session.expires_at)}` : ""} · Chrome queda minimizado para imprimir`
              : waiting
                ? session?.message ||
                  "Usa la ventana de Chrome que se abrió en este equipo"
                : session?.message ||
                  "Se abre una ventana de Chrome para que inicies sesión en Outlook"}
          </p>
        </div>
      </div>
      {connected ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={onDisconnect}
          disabled={busy}
          className="self-start sm:self-auto"
        >
          <Unplug aria-hidden="true" /> Desconectar
        </Button>
      ) : (
        <Button
          size="sm"
          onClick={onConnect}
          disabled={busy || waiting}
          className="self-start sm:self-auto"
        >
          {waiting ? (
            <Loader2 aria-hidden="true" className="animate-spin" />
          ) : (
            <LogIn aria-hidden="true" />
          )}
          {waiting ? "Esperando…" : "Conectar Outlook"}
        </Button>
      )}
    </section>
  );
}
