export type ResourceStatus = "VIRTUAL" | "MATERIALIZED" | "PROVISIONING" | "FAILED";

export interface MediaItem {
  tmdbId: string;
  title: string;
  year?: string;
  rating?: number;
  posterUrl?: string;
  status: ResourceStatus;
  overview?: string;
}

export interface HomeFeed {
  favorites: MediaItem[];
  trending: MediaItem[];
  updatedAt: string;
}

export interface ResourceItem {
  id: string;
  name: string;
  size?: string;
  status: ResourceStatus;
  updatedAt?: string;
  webdavPath?: string;
  errorMessage?: string;
}

export interface QuarkLink {
  id: string;
  title: string;
  shareUrl: string;
  quality?: string;
  size?: string;
  matchScore?: number;
}

export interface TmdbDetail {
  tmdbId: string;
  title: string;
  overview?: string;
  year?: string;
  runtime?: string;
  rating?: number;
  genres?: string[];
  posterUrl?: string;
  backdropUrl?: string;
  resources: ResourceItem[];
}

export interface QuarkSearchParams {
  tmdbId?: string;
  query?: string;
}

export interface RetryOptions {
  retries: number;
  backoffMs: number;
}

export interface ApiClientOptions {
  baseUrl: string;
  timeoutMs: number;
  retry: RetryOptions;
}