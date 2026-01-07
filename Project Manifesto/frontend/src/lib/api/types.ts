export type ResourceStatus = "VIRTUAL" | "MATERIALIZED" | "PROVISIONING" | "FAILED";
export type TaskStatus = "pending" | "processing" | "completed" | "failed";

export interface ApiErrorShape {
  message: string;
  code?: string;
  status?: number;
  requestId?: string;
}

export interface ApiMeta {
  source: "mock" | "backend";
  warning?: string;
}

export interface ApiResult<T> {
  ok: boolean;
  data?: T;
  error?: ApiErrorShape;
  meta?: ApiMeta;
}

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

export type LinkItem = QuarkLink;

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

export interface BackendChannelInfo {
  id: string;
  name: string;
  channelLogo?: string;
  channelId?: string;
}

export interface BackendResourceItem {
  id?: string;
  messageId?: string;
  title?: string;
  content?: string;
  pubDate?: string;
  image?: string;
  cloudLinks?: string[];
  cloudType?: string;
  tags?: string[];
  channel?: string;
  channelId?: string;
}

export interface BackendResourceGroup {
  id: string;
  list: BackendResourceItem[];
  channelInfo: BackendChannelInfo;
}

export interface BackendResourceSearchResponse {
  data: BackendResourceGroup[];
}

export interface TaskRecord {
  taskId: string;
  status: TaskStatus;
  tmdbId: string;
  linkId?: string;
  updatedAt: string;
  progress?: number;
  resultWebdavUrl?: string;
  errorMessage?: string;
}

export interface SaveVirtualLinkParams {
  tmdbId: string;
  linkId: string;
  title: string;
  shareUrl: string;
}

export interface TriggerJitProvisionParams {
  tmdbId: string;
  linkId: string;
  shareUrl?: string;
}

export interface RetryOptions {
  retries: number;
  backoffMs: number;
}

export interface ApiClientOptions {
  baseUrl: string;
  apiBaseUrl: string;
  useMock: boolean;
  timeoutMs: number;
  retry: RetryOptions;
}
