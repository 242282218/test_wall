"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import type { MediaItem } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

export function PosterCard({ item }: { item: MediaItem }) {
  const [imageError, setImageError] = useState(false);
  const posterSrc = !imageError && item.posterUrl
    ? item.posterUrl
    : "/placeholder-poster.svg";

  return (
    <Link href={`/movie/${item.tmdbId}`} className="poster-card">
      <div className="poster-card__image">
        <Image
          src={posterSrc}
          alt={item.title}
          fill
          sizes="(max-width: 768px) 45vw, 200px"
          className="poster-card__img"
          onError={() => setImageError(true)}
        />
        <div className="poster-card__status">
          <StatusBadge status={item.status} />
        </div>
      </div>
      <div className="poster-card__body">
        <h3>{item.title}</h3>
        <p>
          {item.year ? item.year : "Unknown year"}
          {item.rating ? ` ? ${item.rating.toFixed(1)}` : ""}
        </p>
      </div>
    </Link>
  );
}
