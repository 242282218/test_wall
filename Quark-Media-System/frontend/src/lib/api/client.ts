import type {
  ApiClientOptions,
  HomeFeed,
  QuarkLink,
  QuarkSearchParams,
  RetryOptions,
  TmdbDetail
} from "./types";
import { getMockDetail, getMockQuarkLinks, mockHomeFeed } from "./mock";

export class ApiError extends Error {
  status: number;
  payload?: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

const DEFAULT_TIMEOUT_MS = 10000;
const DEFAULT_RETRY: RetryOptions = { retries: 1, backoffMs: 500 };

const rawBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE || process.env.API_BASE || "";
const baseUrl = rawBaseUrl.replace(/\/$/, "");
const useMock = baseUrl.length === 0 || baseUrl === "mock";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithTimeout(
  input: RequestInfo,
  init: RequestInit,
  timeoutMs: number
) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(input, {
      ...init,
      signal: controller.signal
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

function buildQuery(params?: Record<string, string | number | undefined>) {
  if (!params) return "";
  const entries = Object.entries(params).filter(([, value]) => value !== undefined);
  if (entries.length === 0) return "";

  const search = new URLSearchParams();
  for (const [key, value] of entries) {
    search.set(key, String(value));
  }
  const queryString = search.toString();
  return queryString ? `?${queryString}` : "";
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  timeoutMs?: number;
  retry?: RetryOptions;
  headers?: Record<string, string>;
}

async function requestJson<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const url = `${baseUrl}${path}${buildQuery(options.query)}`;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const retry = options.retry ?? DEFAULT_RETRY;

  for (let attempt = 0; attempt <= retry.retries; attempt += 1) {
    try {
      const response = await fetchWithTimeout(
        url,
        {
          method: options.method ?? "GET",
          headers: {
            "Content-Type": "application/json",
            ...(options.headers ?? {})
          },
          body: options.body ? JSON.stringify(options.body) : undefined
        },
        timeoutMs
      );

      if (!response.ok) {
        let payload: unknown = undefined;
        try {
          payload = await response.json();
        } catch {
          payload = await response.text();
        }
        throw new ApiError(
          `Request failed with status ${response.status}`,
          response.status,
          payload
        );
      }

      return (await response.json()) as T;
    } catch (error) {
      if (attempt >= retry.retries) {
        throw error;
      }
      await sleep(retry.backoffMs * (attempt + 1));
    }
  }

  throw new ApiError("Request failed", 500);
}

export function getApiClientConfig(): ApiClientOptions {
  return {
    baseUrl,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    retry: DEFAULT_RETRY
  };
}

export async function getHomeFeed(): Promise<HomeFeed> {
  if (useMock) {
    return mockHomeFeed;
  }

  return requestJson<HomeFeed>("/home");
}

export async function getTmdbDetail(tmdbId: string): Promise<TmdbDetail> {
  if (useMock) {
    return getMockDetail(tmdbId);
  }

  return requestJson<TmdbDetail>(`/media/${tmdbId}`);
}

export async function searchQuarkLinks(
  params: QuarkSearchParams
): Promise<QuarkLink[]> {
  if (useMock) {
    return getMockQuarkLinks(params.tmdbId, params.query);
  }

  return requestJson<QuarkLink[]>("/resources/search", {
    query: {
      tmdb_id: params.tmdbId,
      query: params.query
    }
  });
}