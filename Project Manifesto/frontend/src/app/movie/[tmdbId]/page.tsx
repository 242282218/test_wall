"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { StatusBadge } from "@/components/StatusBadge";
import {
  getApiClientConfig,
  getTaskStatus,
  saveVirtualLink,
  triggerJitProvision,
  type LinkItem,
  type ResourceStatus
} from "@/lib/api";
import { useQuarkLinks } from "@/lib/hooks/useQuarkLinks";
import { useTmdbDetail } from "@/lib/hooks/useTmdbDetail";

const mapTaskStatus = (status: string): ResourceStatus => {
  switch (status) {
    case "pending":
    case "processing":
      return "PROVISIONING";
    case "completed":
      return "MATERIALIZED";
    case "failed":
      return "FAILED";
    default:
      return "PROVISIONING";
  }
};

export default function MovieDetailPage({
  params
}: {
  params: { tmdbId: string };
}) {
  const apiConfig = getApiClientConfig();
  const tmdbId = params.tmdbId;
  const {
    data: detail,
    error,
    isLoading,
    mutate
  } = useTmdbDetail(tmdbId);
  const {
    data: links,
    error: linksError,
    isLoading: linksLoading,
    mutate: retryLinks
  } = useQuarkLinks({ tmdbId });
  const [notice, setNotice] = useState<{
    type: "success" | "error" | "info";
    message: string;
  } | null>(null);
  const [linkStatus, setLinkStatus] = useState<Record<string, ResourceStatus>>(
    {}
  );
  const [linkBusy, setLinkBusy] = useState<Record<string, boolean>>({});
  const [activeTasks, setActiveTasks] = useState<
    Record<string, { linkId: string }>
  >({});
  const noticeTimer = useRef<number | null>(null);

  const setNoticeWithTimeout = (
    next: { type: "success" | "error" | "info"; message: string } | null
  ) => {
    setNotice(next);
    if (noticeTimer.current) {
      window.clearTimeout(noticeTimer.current);
    }
    if (next) {
      noticeTimer.current = window.setTimeout(() => {
        setNotice(null);
      }, 2800);
    }
  };

  const handleSaveVirtual = async (link: LinkItem) => {
    setLinkBusy((prev) => ({ ...prev, [link.id]: true }));
    const result = await saveVirtualLink({
      tmdbId,
      linkId: link.id,
      title: link.title,
      shareUrl: link.shareUrl
    });
    if (result.ok) {
      const nextStatus = result.data?.status ?? "VIRTUAL";
      setLinkStatus((prev) => ({ ...prev, [link.id]: nextStatus }));
      const warning = result.meta?.warning;
      setNoticeWithTimeout({
        type: warning ? "info" : "success",
        message: warning
          ? `Saved as virtual entry. ${warning}`
          : "Saved as virtual entry."
      });
    } else {
      setNoticeWithTimeout({
        type: "error",
        message: result.error?.message || "Save failed."
      });
    }
    setLinkBusy((prev) => ({ ...prev, [link.id]: false }));
  };

  const handleJitProvision = async (link: LinkItem) => {
    setLinkBusy((prev) => ({ ...prev, [link.id]: true }));
    const result = await triggerJitProvision({
      tmdbId,
      linkId: link.id,
      shareUrl: link.shareUrl
    });
    if (result.ok && result.data) {
      const taskRecord = result.data;
      const nextStatus = mapTaskStatus(taskRecord.status);
      setLinkStatus((prev) => ({ ...prev, [link.id]: nextStatus }));
      if (taskRecord.status === "pending" || taskRecord.status === "processing") {
        setActiveTasks((prev) => ({
          ...prev,
          [taskRecord.taskId]: { linkId: link.id }
        }));
      }
      const warning = result.meta?.warning;
      let message = "JIT provisioning started.";
      if (taskRecord.status === "completed") {
        message = "Provisioning completed.";
      } else if (taskRecord.status === "failed") {
        message = "Provisioning failed.";
      }
      setNoticeWithTimeout({
        type: warning ? "info" : "success",
        message: warning
          ? `${message} ${warning}`
          : message
      });
    } else {
      setNoticeWithTimeout({
        type: "error",
        message: result.error?.message || "Provisioning failed."
      });
    }
    setLinkBusy((prev) => ({ ...prev, [link.id]: false }));
  };

  useEffect(() => {
    const taskIds = Object.keys(activeTasks);
    if (taskIds.length === 0) {
      return;
    }

    let cancelled = false;

    const pollTasks = async () => {
      const updates: Record<string, ResourceStatus> = {};
      let tasksChanged = false;
      const nextTasks = { ...activeTasks };

      const results = await Promise.all(
        taskIds.map(async (taskId) => ({
          taskId,
          result: await getTaskStatus(taskId)
        }))
      );

      if (cancelled) {
        return;
      }

      results.forEach(({ taskId, result }) => {
        const linkId = activeTasks[taskId]?.linkId;
        if (!linkId) {
          delete nextTasks[taskId];
          tasksChanged = true;
          return;
        }

        if (!result.ok || !result.data) {
          updates[linkId] = "FAILED";
          delete nextTasks[taskId];
          tasksChanged = true;
          setNoticeWithTimeout({
            type: "error",
            message: result.error?.message || "Task status unavailable."
          });
          return;
        }

        const mappedStatus = mapTaskStatus(result.data.status);
        updates[linkId] = mappedStatus;

        if (result.data.status === "completed") {
          delete nextTasks[taskId];
          tasksChanged = true;
          if (!apiConfig.useMock) {
            mutate();
          }
          setNoticeWithTimeout({
            type: "success",
            message: "Provisioning completed."
          });
        } else if (result.data.status === "failed") {
          delete nextTasks[taskId];
          tasksChanged = true;
          setNoticeWithTimeout({
            type: "error",
            message: result.data.errorMessage || "Provisioning failed."
          });
        }
      });

      if (Object.keys(updates).length > 0) {
        setLinkStatus((prev) => ({ ...prev, ...updates }));
      }

      if (tasksChanged) {
        setActiveTasks(nextTasks);
      }
    };

    pollTasks();
    const intervalId = window.setInterval(pollTasks, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [activeTasks, apiConfig.useMock, mutate]);

  const firstLink = links && links.length > 0 ? links[0] : null;

  if (isLoading) {
    return <LoadingState label="Loading detail page" />;
  }

  if (error || !detail) {
    return (
      <ErrorState
        title="Detail not available"
        description="We could not load the media detail yet."
        onRetry={() => mutate()}
      />
    );
  }

  return (
    <div>
      <section className="detail-hero">
        <div className="detail-hero__poster">
          <Image
            src={detail.posterUrl || "/placeholder-poster.svg"}
            alt={detail.title}
            fill
            sizes="(max-width: 768px) 60vw, 280px"
            className="detail-hero__poster-img"
            priority
          />
        </div>
        <div className="detail-hero__content">
          <div>
            <h1 className="section__title">{detail.title}</h1>
            <div className="detail-hero__meta">
              {detail.year ? <span>{detail.year}</span> : null}
              {detail.runtime ? <span>{detail.runtime}</span> : null}
              {detail.rating ? <span>{detail.rating.toFixed(1)} rating</span> : null}
            </div>
          </div>
          {detail.overview ? <p>{detail.overview}</p> : null}
          {detail.genres && detail.genres.length > 0 ? (
            <div className="detail-hero__meta">
              {detail.genres.map((genre) => (
                <span key={genre}>{genre}</span>
              ))}
            </div>
          ) : null}
          <div className="detail-actions">
            <button
              className="button"
              type="button"
              onClick={() => firstLink && handleSaveVirtual(firstLink)}
              disabled={!firstLink || linksLoading}
            >
              Save (Virtual)
            </button>
            <button
              className="button button--ghost"
              type="button"
              onClick={() => firstLink && handleJitProvision(firstLink)}
              disabled={!firstLink || linksLoading}
            >
              Watch Now (JIT)
            </button>
          </div>
        </div>
      </section>

      {notice ? (
        <NoticeBanner
          type={notice.type}
          message={notice.message}
          onClose={() => setNotice(null)}
        />
      ) : null}

      <section className="section card">
        <div className="section__header">
          <div>
            <h2 className="section__title">Auto Search Links</h2>
            <p className="section__subtitle">
              Triggered when you open the detail page.
            </p>
          </div>
        </div>

        {linksLoading ? (
          <LoadingState label="Searching Quark links" />
        ) : linksError ? (
          <ErrorState
            title="Search failed"
            description="We could not fetch Quark share links."
            onRetry={() => retryLinks()}
          />
        ) : links && links.length > 0 ? (
          <div className="link-list">
            {links.map((link) => (
              <div key={link.id} className="link-item">
                <div className="link-item__meta">
                  <strong>{link.title}</strong>
                  <span>
                    {link.quality || "Unknown quality"} - {link.size || "--"}
                  </span>
                </div>
                <div className="link-item__actions">
                  <div className="link-item__status">
                    {linkStatus[link.id] ? (
                      <StatusBadge status={linkStatus[link.id]} />
                    ) : (
                      <span className="link-item__hint">Not saved</span>
                    )}
                  </div>
                  <div className="link-item__buttons">
                    <button
                      className="button button--ghost"
                      type="button"
                      onClick={() => handleSaveVirtual(link)}
                      disabled={linkBusy[link.id]}
                    >
                      Save (Virtual)
                    </button>
                    <button
                      className="button"
                      type="button"
                      onClick={() => handleJitProvision(link)}
                      disabled={linkBusy[link.id]}
                    >
                      Watch Now
                    </button>
                    <a
                      className="button button--ghost"
                      href={link.shareUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open Link
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyLinks />
        )}
      </section>

      <section className="section card">
        <div className="section__header">
          <div>
            <h2 className="section__title">Resource Map</h2>
            <p className="section__subtitle">
              Virtual vs materialized status across files.
            </p>
          </div>
        </div>
        <div className="resource-list">
          {detail.resources.map((resource) => (
            <div key={resource.id} className="resource-item">
              <div className="resource-item__meta">
                <strong>{resource.name}</strong>
                <span>
                  {resource.size || "--"} -
                  {resource.updatedAt
                    ? ` Updated ${new Date(resource.updatedAt).toLocaleString()}`
                    : " Updated time unknown"}
                </span>
                {resource.errorMessage ? (
                  <span>{resource.errorMessage}</span>
                ) : null}
              </div>
              <div className="resource-item__meta">
                <StatusBadge status={resource.status} />
                {resource.status === "FAILED" ? (
                  <button className="button button--ghost" type="button">
                    Retry
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function EmptyLinks() {
  return (
    <div className="state state--empty">
      <h3>No links found yet</h3>
      <p>Try refreshing or check the search API configuration.</p>
    </div>
  );
}

function NoticeBanner({
  type,
  message,
  onClose
}: {
  type: "success" | "error" | "info";
  message: string;
  onClose: () => void;
}) {
  return (
    <div className={`notice notice--${type}`}>
      <span>{message}</span>
      <button className="button button--ghost" onClick={onClose} type="button">
        Dismiss
      </button>
    </div>
  );
}
