"use client";

import useSWR from "swr";
import { getTmdbDetail } from "@/lib/api";

export function useTmdbDetail(tmdbId?: string) {
  return useSWR(
    tmdbId ? ["tmdb-detail", tmdbId] : null,
    () => getTmdbDetail(tmdbId as string)
  );
}