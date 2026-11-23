import { ExternalLink } from "lucide-react";
import { formatDay, formatPostTime } from "@/lib/forums";
import { cn } from "@/lib/utils";
import type { ForumContribution } from "@/types/api";

function StatusBadge({ item }: { item: ForumContribution }) {
  const days = item.business_days_waiting;
  const { label, className } = (() => {
    switch (item.status) {
      case "vencido":
        return {
          label: `Vencido · ${days} ${days === 1 ? "día hábil" : "días hábiles"}`,
          className: "border-danger-border bg-danger-soft text-danger-fg",
        };
      case "vence_hoy":
        return { label: "Vence hoy", className: "border-caution-border bg-caution-soft text-caution-fg" };
      case "a_tiempo":
        return {
          label: item.reply_due ? `A tiempo · vence ${formatDay(item.reply_due)}` : "A tiempo",
          className: "border-info-border bg-info-soft text-info-fg",
        };
      case "respondido_tarde":
        return { label: "Respondido tarde", className: "border-notice-border bg-notice-soft text-notice-fg" };
      default:
        return { label: "Respondido", className: "border-ok-border bg-ok-soft text-ok-fg" };
    }
  })();
  return (
    <span className={cn("inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-medium", className)}>
      {label}
    </span>
  );
}

function GradeBadge({ item }: { item: ForumContribution }) {
  if (!item.gradable) return null;
  return item.grade === null ? (
    <span className="inline-flex shrink-0 items-center rounded-full border border-pending-border bg-pending-soft px-2 py-0.5 text-xs font-medium text-pending-fg">
      Sin nota
    </span>
  ) : (
    <span className="inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-medium text-muted-foreground">
      Nota {item.grade}
    </span>
  );
}

interface ContributionListProps {
  items: ForumContribution[];
  emptyMessage: string;
}

export function ContributionList({ items, emptyMessage }: ContributionListProps) {
  if (items.length === 0) {
    return <p className="px-4 py-10 text-center text-sm text-muted-foreground">{emptyMessage}</p>;
  }
  return (
    <ul className="divide-y">
      {items.map((item) => (
        <li key={item.post_id} className="space-y-2 px-4 py-3">
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
            <div className="min-w-0">
              <p className="text-sm font-semibold capitalize leading-snug">{item.author_name.toLowerCase()}</p>
              <p className="line-clamp-2 text-xs text-muted-foreground">
                {item.parent_id === null ? "Abrió" : "Respondió en"} «{item.discussion_title}»
                {item.created_at && <> · {formatPostTime(item.created_at)}</>}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <StatusBadge item={item} />
              <GradeBadge item={item} />
            </div>
          </div>
          {item.excerpt && (
            <p className="line-clamp-3 text-sm leading-relaxed text-foreground/85">{item.excerpt}</p>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>
              {item.first_reply_at
                ? `Tu réplica: ${formatPostTime(item.first_reply_at)}`
                : item.reply_due && `Plazo para responder: ${formatDay(item.reply_due)}`}
            </span>
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-medium text-primary underline-offset-2 hover:underline"
            >
              Abrir en Zajuna
              <ExternalLink aria-hidden="true" className="h-3.5 w-3.5" />
              <span className="sr-only">(se abre en otra pestaña)</span>
            </a>
          </div>
        </li>
      ))}
    </ul>
  );
}
