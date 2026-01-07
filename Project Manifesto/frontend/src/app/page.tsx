"use client";

import { PosterCard } from "@/components/PosterCard";
import { LoadingState } from "@/components/LoadingState";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { useHomeFeed } from "@/lib/hooks/useHomeFeed";

export default function HomePage() {
  const { data, error, isLoading, mutate } = useHomeFeed();

  if (isLoading) {
    return <LoadingState label="Loading poster wall" />;
  }

  if (error || !data) {
    return (
      <ErrorState
        title="Unable to load the poster wall"
        description="Check your API connection or retry."
        onRetry={() => mutate()}
      />
    );
  }

  return (
    <div>
      <section className="section">
        <div className="section__header">
          <div>
            <h2 className="section__title">Your Library</h2>
            <p className="section__subtitle">
              Favorites first, virtual items stay lightweight.
            </p>
          </div>
          <span className="section__subtitle">
            Updated {new Date(data.updatedAt).toLocaleString()}
          </span>
        </div>
        {data.favorites.length === 0 ? (
          <EmptyState
            title="No favorites yet"
            description="Save links from the detail page to populate this row."
          />
        ) : (
          <div className="poster-grid">
            {data.favorites.map((item) => (
              <PosterCard key={item.tmdbId} item={item} />
            ))}
          </div>
        )}
      </section>

      <section className="section">
        <div className="section__header">
          <div>
            <h2 className="section__title">Trending Drops</h2>
            <p className="section__subtitle">
              Auto-curated picks ready for search and provision.
            </p>
          </div>
        </div>
        <div className="poster-grid">
          {data.trending.map((item) => (
            <PosterCard key={item.tmdbId} item={item} />
          ))}
        </div>
      </section>
    </div>
  );
}