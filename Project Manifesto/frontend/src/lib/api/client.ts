import type {
  ApiClientOptions,
  ApiErrorShape,
  ApiMeta,
  ApiResult,
  BackendResourceSearchResponse,
  HomeFeed,
  LinkItem,
  QuarkSearchParams,
  ResourceStatus,
  RetryOptions,
  SaveVirtualLinkParams,
  TaskRecord,
  TriggerJitProvisionParams,
  TmdbDetail
} from "./types";
import { getMockDetail, getMockQuarkLinks, mockHomeFeed } from "./mock";

export class ApiError extends Error {
  status: number;
  payload?: unknown;
  requestId?: string;

  constructor(message: string, status: number, payload?: unknown, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
    this.requestId = requestId;
  }
}

const DEFAULT_TIMEOUT_MS = 10000;
const DEFAULT_RETRY: RetryOptions = { retries: 1, backoffMs: 500 };

const rawBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE || process.env.API_BASE || "";
const baseUrl = rawBaseUrl.replace(/\/$/, "");
const useMock = baseUrl.length === 0 || baseUrl === "mock";
const apiBaseUrl = useMock
  ? ""
  : baseUrl.endsWith("/api/v1")
    ? baseUrl
    : `${baseUrl}/api/v1`;
const mockTasks = new Map<string, TaskRecord>();

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

function ok<T>(data: T, meta?: ApiMeta): ApiResult<T> {
  return { ok: true, data, meta };
}

function fail(
  message: string,
  status?: number,
  code?: string,
  requestId?: string
): ApiResult<never> {
  const error: ApiErrorShape = { message, status, code, requestId };
  return { ok: false, error };
}

async function requestJson<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const url = `${apiBaseUrl}${path}${buildQuery(options.query)}`;
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
        const requestId = response.headers.get("x-request-id") ?? undefined;
        let payload: unknown = undefined;
        try {
          payload = await response.json();
        } catch {
          payload = await response.text();
        }
        throw new ApiError(
          `Request failed with status ${response.status}`,
          response.status,
          payload,
          requestId
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
    apiBaseUrl,
    useMock,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    retry: DEFAULT_RETRY
  };
}

function buildMockWarning(action: string) {
  if (useMock) {
    return `API_BASE not configured; using mock for ${action}.`;
  }
  return `Mock in use for ${action}.`;
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
): Promise<LinkItem[]> {
  if (useMock) {
    return getMockQuarkLinks(params.tmdbId, params.query);
  }

  const keyword = params.query ?? params.tmdbId ?? "";
  if (!keyword) {
    return [];
  }

  const response = await requestJson<BackendResourceSearchResponse>(
    "/resources/search",
    {
      query: { keyword }
    }
  );

  const links: LinkItem[] = [];
  response.data.forEach((group) => {
    group.list.forEach((item, itemIndex) => {
      const title = item.title || item.content || "Untitled";
      const baseId = item.id || item.messageId || `${group.id}-${itemIndex}`;
      (item.cloudLinks ?? []).forEach((link, linkIndex) => {
        links.push({
          id: `${baseId}-${linkIndex}`,
          title,
          shareUrl: link,
        });
      });
    });
  });

  return links;
}

export async function saveVirtualLink(
  params: SaveVirtualLinkParams
): Promise<ApiResult<{ status: ResourceStatus; savedAt: string }>> {
  if (useMock) {
    return ok(
      { status: "VIRTUAL", savedAt: new Date().toISOString() },
      { source: "mock", warning: buildMockWarning("saveVirtualLink") }
    );
  }

  try {
    const data = await requestJson<{ status: ResourceStatus; savedAt: string }>(
      `/media/${params.tmdbId}/links/virtual`,
      {
        method: "POST",
        body: params
      }
    );
    return ok(data, { source: "backend" });
  } catch (error) {
    if (error instanceof ApiError) {
      return fail(error.message, error.status, undefined, error.requestId);
    }
    return fail("Failed to save virtual link");
  }
}

export async function triggerJitProvision(
  params: TriggerJitProvisionParams
): Promise<ApiResult<TaskRecord>> {
  if (useMock) {
    const taskId = `task_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const record: TaskRecord = {
      taskId,
      status: "processing",
      tmdbId: params.tmdbId,
      linkId: params.linkId,
      updatedAt: new Date().toISOString()
    };
    mockTasks.set(taskId, record);
    return ok(record, {
      source: "mock",
      warning: buildMockWarning("triggerJitProvision")
    });
  }

  try {
    const data = await requestJson<TaskRecord>(
      `/media/${params.tmdbId}/provision`,
      {
        method: "POST",
        body: params
      }
    );
    if (!data.taskId) {
      throw new ApiError("Missing taskId in response", 500, data);
    }
    return ok(data, { source: "backend" });
  } catch (error) {
    if (error instanceof ApiError) {
      return fail(error.message, error.status, undefined, error.requestId);
    }
    return fail("Failed to trigger JIT provisioning");
  }
}

export async function getTaskStatus(
  taskId: string
): Promise<ApiResult<TaskRecord>> {
  if (useMock) {
    const record = mockTasks.get(taskId);
    if (!record) {
      return fail("Task not found", 404, "TASK_NOT_FOUND");
    }
    return ok(record, { source: "mock" });
  }

  try {
    const data = await requestJson<TaskRecord>(`/tasks/${taskId}`);
    return ok(data, { source: "backend" });
  } catch (error) {
    if (error instanceof ApiError) {
      return fail(error.message, error.status, undefined, error.requestId);
    }
    return fail("Failed to fetch task status");
  }
}
