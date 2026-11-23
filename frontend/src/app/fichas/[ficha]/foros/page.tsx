"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, MessagesSquare, RotateCw, Search } from "lucide-react";
import { ContributionList } from "@/components/forums/contribution-list";
import { Topbar } from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { checkForum, fetchForumInbox, fetchForums } from "@/lib/api";
import { describeForumError, needsReply, sortByUrgency } from "@/lib/forums";
import { cn } from "@/lib/utils";
import type { ForumInboxResponse, ForumListResponse, ForumSummaryItem } from "@/types/api";

type View = "por_responder" | "todos";

/** En una sola columna (bajo xl) la bandeja queda debajo de la lista: hay que llevar la vista a ella. */
function revealBelowList(el: HTMLElement | null) {
  if (!el || window.matchMedia("(min-width: 1280px)").matches) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
}

function lastCheck(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

function ForumRow({
  forum,
  active,
  busy,
  disabled,
  onOpen,
  onCheck,
}: {
  forum: ForumSummaryItem;
  active: boolean;
  busy: boolean;
  disabled: boolean;
  onOpen: () => void;
  onCheck: () => void;
}) {
  const counts = forum.counts;
  const pending = counts ? counts.overdue + counts.due_today + counts.on_time : 0;
  return (
    <li
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 transition-colors duration-150",
        active ? "bg-accent/60" : "hover:bg-muted/40",
      )}
    >
      <button
        type="button"
        onClick={onOpen}
        aria-current={active ? "true" : undefined}
        className="min-w-0 flex-[1_1_15rem] text-left"
      >
        <span className="block text-sm font-medium leading-snug">{forum.name}</span>
        <span className="mt-0.5 block text-xs text-muted-foreground">
          {forum.checked_at ? `Revisado ${lastCheck(forum.checked_at)}` : "Sin revisar"}
          {!forum.graded && " · sin nota"}
        </span>
      </button>
      <div className="ml-auto flex items-center gap-2">
        {counts && counts.overdue > 0 && (
          <span className="rounded-full border border-danger-border bg-danger-soft px-2 py-0.5 text-xs font-semibold tabular-nums text-danger-fg">
            {counts.overdue} vencidos
          </span>
        )}
        {counts && counts.overdue === 0 && pending > 0 && (
          <span className="rounded-full border border-caution-border bg-caution-soft px-2 py-0.5 text-xs font-semibold tabular-nums text-caution-fg">
            {pending} por responder
          </span>
        )}
        {counts && pending === 0 && counts.contributions > 0 && (
          <span className="rounded-full border border-ok-border bg-ok-soft px-2 py-0.5 text-xs font-medium text-ok-fg">
            Al día
          </span>
        )}
        <Button size="sm" variant="outline" onClick={onCheck} disabled={disabled}>
          {busy ? <RotateCw aria-hidden="true" className="animate-spin" /> : <Search aria-hidden="true" />}
          {busy ? "Revisando…" : forum.checked_at ? "Revisar de nuevo" : "Revisar"}
        </Button>
      </div>
    </li>
  );
}

export default function ForosPage() {
  const params = useParams();
  const ficha = params.ficha as string;
  const router = useRouter();
  // ?f= llega desde Alertas: abre la bandeja de ese foro
  const queryForum = Number(useSearchParams().get("f")) || null;

  const [list, setList] = useState<ForumListResponse | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(queryForum);
  const [loadedInbox, setInbox] = useState<ForumInboxResponse | null>(null);
  const [queue, setQueue] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("por_responder");
  const [showAll, setShowAll] = useState(false);
  const checking = queue.length > 0;
  const inboxRef = useRef<HTMLElement>(null);
  // Al llegar desde Alertas (?f=) o al elegir un foro se lleva la vista a su bandeja
  const pendingReveal = useRef(queryForum !== null);

  useEffect(() => {
    fetchForums(ficha)
      .then((data) => {
        setList(data);
        setSelectedId((current) => current ?? data.forums.find((f) => f.graded && f.checked_at)?.forum_id ?? null);
      })
      .catch((e) =>
        setError(
          String(e?.message).includes("404")
            ? "Este grupo todavía no tiene el mapeo de evidencias. Sincronízalo desde el dashboard."
            : describeForumError(e),
        ),
      );
  }, [ficha]);

  // Al cambiar de foro se carga su última revisión guardada (sin entrar a Zajuna)
  const selected = list?.forums.find((f) => f.forum_id === selectedId) ?? null;
  const selectedChecked = selected?.checked_at ?? null;
  useEffect(() => {
    if (selectedId === null || !selectedChecked) return;
    let cancelled = false;
    fetchForumInbox(ficha, selectedId)
      .then((data) => !cancelled && setInbox(data))
      .catch((e) => !cancelled && setError(describeForumError(e)));
    return () => {
      cancelled = true;
    };
  }, [ficha, selectedId, selectedChecked]);
  // La bandeja cargada vale solo si es del foro elegido y de su última revisión
  const inbox =
    loadedInbox && loadedInbox.forum_id === selectedId && loadedInbox.checked_at === selectedChecked
      ? loadedInbox
      : null;
  const inboxLoading = selectedChecked !== null && inbox === null;

  // Se espera a que la bandeja tenga su contenido: con ella a medio cargar el scroll se queda corto
  const inboxReady = list !== null && !inboxLoading;
  useEffect(() => {
    if (!pendingReveal.current || !inboxReady) return;
    pendingReveal.current = false;
    revealBelowList(inboxRef.current);
  }, [inboxReady, selectedId]);

  const openForum = useCallback(
    (forumId: number) => {
      setSelectedId(forumId);
      setView("por_responder");
      router.replace(`/fichas/${ficha}/foros?f=${forumId}`, { scroll: false });
      if (forumId === selectedId) revealBelowList(inboxRef.current);
      else pendingReveal.current = true;
    },
    [ficha, router, selectedId],
  );

  const runChecks = useCallback(
    async (forumIds: number[]) => {
      if (forumIds.length === 0) return;
      setError(null);
      setQueue(forumIds);
      const failed: string[] = [];
      for (const forumId of forumIds) {
        try {
          const result = await checkForum(ficha, forumId);
          setList((prev) =>
            prev && {
              ...prev,
              forums: prev.forums.map((f) =>
                f.forum_id === forumId ? { ...f, checked_at: result.checked_at, counts: result.counts } : f,
              ),
            },
          );
          // La bandeja abierta se recarga sola al cambiar su checked_at
          setSelectedId((current) => current ?? forumId);
        } catch (e) {
          const name = list?.forums.find((f) => f.forum_id === forumId)?.name ?? `Foro ${forumId}`;
          failed.push(`${name}: ${describeForumError(e)}`);
        }
        setQueue((prev) => prev.slice(1));
      }
      if (failed.length) setError(failed.join(" "));
    },
    [ficha, list],
  );

  const forums = useMemo(() => list?.forums ?? [], [list]);
  const visibleForums = showAll ? forums : forums.filter((f) => f.graded);
  const hiddenForums = forums.length - visibleForums.length;

  const contributions = useMemo(() => sortByUrgency(inbox?.contributions ?? []), [inbox]);
  const toReply = contributions.filter(needsReply);
  const rows = view === "por_responder" ? toReply : contributions;

  const totals = useMemo(() => {
    const checked = forums.filter((f) => f.counts);
    return {
      checked: checked.length,
      overdue: checked.reduce((n, f) => n + (f.counts?.overdue ?? 0), 0),
      pending: checked.reduce(
        (n, f) => n + (f.counts ? f.counts.overdue + f.counts.due_today + f.counts.on_time : 0),
        0,
      ),
    };
  }, [forums]);

  if (!list && !error) {
    return (
      <>
        <Topbar title="Foros" />
        <div className="space-y-4 p-4 sm:p-6">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </>
    );
  }

  return (
    <>
      <Topbar
        title="Foros"
        description="Aportes de aprendices que esperan tu réplica. SAVA pide responder en máximo 1 día hábil (sin fines de semana ni festivos). Solo se lee Zajuna: aquí no se publica nada."
      />
      <div className="space-y-5 overflow-hidden p-4 sm:p-6">
        {error && (
          <div
            role="alert"
            className="rounded-md border border-danger-border bg-danger-soft px-4 py-3 text-sm font-medium text-danger-fg"
          >
            {error}
          </div>
        )}

        {totals.checked > 0 && (
          <dl className="grid grid-cols-3 divide-x overflow-hidden rounded-xl border bg-card shadow-card">
            <div className="px-4 py-3">
              <dt className="text-xs text-muted-foreground">Foros revisados</dt>
              <dd className="mt-1 text-2xl font-bold tabular-nums tracking-tight">{totals.checked}</dd>
            </div>
            <div className="px-4 py-3">
              <dt className="text-xs text-muted-foreground">Por responder</dt>
              <dd className="mt-1 text-2xl font-bold tabular-nums tracking-tight">{totals.pending}</dd>
            </div>
            <div className="px-4 py-3">
              <dt className="text-xs text-muted-foreground">Vencidos</dt>
              <dd
                className={cn(
                  "mt-1 text-2xl font-bold tabular-nums tracking-tight",
                  totals.overdue > 0 ? "text-danger-fg" : "text-ok-fg",
                )}
              >
                {totals.overdue}
              </dd>
            </div>
          </dl>
        )}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <section className="self-start overflow-hidden rounded-xl border bg-card shadow-card">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
              <h2 className="text-sm font-semibold">Foros del grupo</h2>
              <Button
                size="sm"
                onClick={() => runChecks(visibleForums.map((f) => f.forum_id))}
                disabled={checking || visibleForums.length === 0}
              >
                <Search aria-hidden="true" />
                {checking
                  ? `Revisando ${visibleForums.length - queue.length + 1} de ${visibleForums.length}`
                  : `Revisar los ${visibleForums.length}`}
              </Button>
            </div>
            {visibleForums.length === 0 ? (
              <p className="px-4 py-10 text-center text-sm text-muted-foreground">
                Este grupo no tiene foros calificables en el mapeo.
              </p>
            ) : (
              <ul className="divide-y">
                {visibleForums.map((forum) => (
                  <ForumRow
                    key={forum.forum_id}
                    forum={forum}
                    active={forum.forum_id === selectedId}
                    busy={queue[0] === forum.forum_id}
                    disabled={checking}
                    onOpen={() => openForum(forum.forum_id)}
                    onCheck={() => {
                      openForum(forum.forum_id);
                      runChecks([forum.forum_id]);
                    }}
                  />
                ))}
              </ul>
            )}
            {(hiddenForums > 0 || showAll) && (
              <div className="border-t px-4 py-2.5">
                <button
                  type="button"
                  onClick={() => setShowAll((v) => !v)}
                  className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                >
                  {showAll
                    ? "Ver solo los foros calificables"
                    : `Mostrar también ${hiddenForums} foros sin nota (anuncios, dudas, social)`}
                </button>
              </div>
            )}
          </section>

          <section
            ref={inboxRef}
            className="scroll-mt-20 self-start overflow-hidden rounded-xl border bg-card shadow-card"
          >
            {!selected ? (
              <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
                <MessagesSquare aria-hidden="true" className="h-8 w-8 text-muted-foreground" />
                <p className="max-w-sm text-sm text-muted-foreground">
                  Elige un foro y revísalo para ver los aportes que esperan tu réplica, del más urgente al más
                  reciente.
                </p>
              </div>
            ) : (
              <>
                <div className="space-y-3 border-b px-4 py-3">
                  <div>
                    <h2 className="text-sm font-semibold leading-snug">{selected.name}</h2>
                    {inbox && (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {inbox.total_discussions} discusiones · {inbox.counts.contributions} aportes ·{" "}
                        {inbox.peer_replies} respuestas entre compañeros · revisado {lastCheck(inbox.checked_at)}
                      </p>
                    )}
                  </div>
                  {inbox && (
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div role="radiogroup" aria-label="Qué mostrar" className="inline-flex rounded-full border p-0.5">
                        {(
                          [
                            ["por_responder", `Por responder (${toReply.length})`],
                            ["todos", `Todos (${contributions.length})`],
                          ] as const
                        ).map(([value, label]) => (
                          <button
                            key={value}
                            type="button"
                            role="radio"
                            aria-checked={view === value}
                            onClick={() => setView(value)}
                            className={cn(
                              "h-7 rounded-full px-3 text-xs font-medium transition-colors duration-150 ease-out",
                              view === value
                                ? "bg-primary text-primary-foreground"
                                : "text-muted-foreground hover:text-foreground",
                            )}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      {inbox.counts.ungraded > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {inbox.counts.ungraded} {inbox.counts.ungraded === 1 ? "aporte" : "aportes"} sin nota
                        </span>
                      )}
                    </div>
                  )}
                  {inbox && inbox.failed_discussions.length > 0 && (
                    <p className="flex items-start gap-2 rounded-md border border-caution-border bg-caution-soft px-3 py-2 text-xs text-caution-fg">
                      <AlertTriangle aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      Zajuna no dejó leer {inbox.failed_discussions.length}{" "}
                      {inbox.failed_discussions.length === 1 ? "discusión" : "discusiones"}. Revisa el foro de nuevo
                      para completarlo.
                    </p>
                  )}
                </div>
                {inboxLoading && !inbox ? (
                  <div className="space-y-3 p-4">
                    <Skeleton className="h-20 rounded-lg" />
                    <Skeleton className="h-20 rounded-lg" />
                  </div>
                ) : !inbox ? (
                  <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
                    <p className="max-w-sm text-sm text-muted-foreground">
                      Este foro todavía no se ha revisado. La revisión lee todas sus discusiones en Zajuna y tarda
                      cerca de un segundo por discusión.
                    </p>
                    <Button onClick={() => runChecks([selected.forum_id])} disabled={checking}>
                      <Search aria-hidden="true" />
                      {queue[0] === selected.forum_id ? "Revisando…" : "Revisar este foro"}
                    </Button>
                  </div>
                ) : (
                  <ContributionList
                    items={rows}
                    emptyMessage={
                      view === "por_responder"
                        ? contributions.length > 0
                          ? "Todos los aportes de este foro ya tienen tu réplica."
                          : "Este foro todavía no tiene aportes de aprendices."
                        : "Este foro todavía no tiene aportes de aprendices."
                    }
                  />
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
