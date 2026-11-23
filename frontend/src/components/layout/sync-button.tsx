"use client";

import { useState } from "react";
import { RefreshCw, Loader2 } from "lucide-react";
import { triggerScraper } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useSyncProgress } from "@/components/layout/sync-progress";

interface SyncButtonProps {
  fichas?: string[];
  label?: string;
  compact?: boolean;
  onComplete?: () => void;
}

export function SyncButton({
  fichas,
  label = "Sincronizar",
  compact = false,
  onComplete,
}: SyncButtonProps) {
  const { isRunning, start } = useSyncProgress();
  const [triggering, setTriggering] = useState(false);

  const handleClick = async () => {
    if (isRunning || triggering) return;
    setTriggering(true);
    try {
      const job = await triggerScraper(fichas);
      // Seguir ESTE job por id — evita pintar el progreso de un job ajeno
      start(onComplete ?? (() => window.location.reload()), job.job_id);
    } catch (e) {
      // 409 = ya hay un job corriendo (quizá de otra pestaña): adoptarlo
      if (e instanceof Error && e.message.includes("409")) {
        start(onComplete ?? (() => window.location.reload()), null);
      }
    } finally {
      setTriggering(false);
    }
  };

  const disabled = isRunning || triggering;

  const icon = disabled ? (
    <Loader2 aria-hidden="true" className="animate-spin" />
  ) : (
    <RefreshCw aria-hidden="true" />
  );

  return (
    <Button
      onClick={handleClick}
      disabled={disabled}
      variant={compact ? "outline" : "primary"}
      size={compact ? "md" : "sm"}
      pill
    >
      {icon}
      {label}
    </Button>
  );
}
