import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function completionColor(pct: number): string {
  if (pct >= 80) return "text-ok-fg";
  if (pct >= 50) return "text-warn-fg";
  return "text-danger-fg";
}

export function completionBg(pct: number): string {
  if (pct >= 80) return "bg-ok";
  if (pct >= 50) return "bg-warn";
  return "bg-danger";
}

export function timeAgo(isoDate: string | null): string {
  if (!isoDate) return "Sin datos";
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "Hace un momento";
  if (diffMin < 60) return `Hace ${diffMin} min`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `Hace ${diffHr}h`;
  const diffDays = Math.floor(diffHr / 24);
  return `Hace ${diffDays}d`;
}

export function shortCourseName(name: string): string {
  return name.replace(/\.\s*\(\d{7}\)$/, "").trim();
}
