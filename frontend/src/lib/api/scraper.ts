import type { ScraperStatus } from "@/types/api";

import { apiFetch, apiPost } from "./core";

export function triggerScraper(fichas?: string[]) {
  return apiPost<ScraperStatus>("/api/scraper/run", {
    fichas: fichas ?? null,
  });
}

export function fetchScraperStatus() {
  return apiFetch<ScraperStatus>("/api/scraper/status");
}
