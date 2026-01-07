"use client";

import useSWR from "swr";
import { getHomeFeed } from "@/lib/api";

export function useHomeFeed() {
  return useSWR("home-feed", getHomeFeed);
}