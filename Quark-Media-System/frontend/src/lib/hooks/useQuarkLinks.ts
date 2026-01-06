"use client";

import useSWR from "swr";
import { searchQuarkLinks } from "@/lib/api";

export function useQuarkLinks(params: { tmdbId?: string; query?: string }) {
  const key = params.tmdbId || params.query
    ? ["quark-links", params.tmdbId, params.query]
    : null;

  return useSWR(key, () => searchQuarkLinks(params));
}