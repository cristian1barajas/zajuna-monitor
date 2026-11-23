"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Topbar } from "@/components/layout/topbar";
import { ActivityTable } from "@/components/activity/activity-table";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchActivity, fetchHealth } from "@/lib/api";
import type { ActivityResponse } from "@/types/api";

export default function FichaActivityPage() {
  const params = useParams();
  const ficha = params.ficha as string;
  const [data, setData] = useState<ActivityResponse | null>(null);
  const [lastScrape, setLastScrape] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchActivity(ficha), fetchHealth()])
      .then(([activity, health]) => {
        setData(activity);
        setLastScrape(health.last_scrape);
      })
      .catch((e) => setError(e.message));
  }, [ficha]);

  if (error) {
    return (
      <>
        <Topbar title="Actividad" />
        <div className="p-6">
          <div className="rounded-lg border border-danger-border bg-danger-soft p-4 text-sm text-danger-fg">
            {error}
          </div>
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Topbar title="Actividad" />
        <div className="space-y-4 p-6">
          <Skeleton className="h-96 rounded-lg" />
        </div>
      </>
    );
  }

  return (
    <>
      <Topbar title="Actividad" lastScrape={lastScrape} description="Último acceso de cada aprendiz a Zajuna, para detectar a quién hacerle seguimiento." />
      <div className="space-y-5 p-6">
        <ActivityTable participants={data.participants} />
      </div>
    </>
  );
}
