import type { HomeFeed, MediaItem, QuarkLink, ResourceItem, TmdbDetail } from "./types";

const now = new Date().toISOString();

const basePoster = "/placeholder-poster.svg";
const baseBackdrop = "/placeholder-backdrop.svg";

const favorites: MediaItem[] = [
  {
    tmdbId: "872585",
    title: "Signal Drift",
    year: "2024",
    rating: 8.2,
    posterUrl: basePoster,
    status: "MATERIALIZED",
    overview: "A deep space rescue mission goes sideways."
  },
  {
    tmdbId: "114399",
    title: "Afterglow Harbor",
    year: "2023",
    rating: 7.6,
    posterUrl: basePoster,
    status: "VIRTUAL",
    overview: "A coastal town hides a forgotten archive."
  }
];

const trending: MediaItem[] = [
  {
    tmdbId: "603",
    title: "Neon Relay",
    year: "2025",
    rating: 8.8,
    posterUrl: basePoster,
    status: "PROVISIONING",
    overview: "Couriers race through a collapsing city grid."
  },
  {
    tmdbId: "980489",
    title: "Garden of Echoes",
    year: "2022",
    rating: 7.3,
    posterUrl: basePoster,
    status: "VIRTUAL",
    overview: "A botanist decodes a sentient greenhouse."
  },
  {
    tmdbId: "42222",
    title: "Prairie Night",
    year: "2021",
    rating: 6.9,
    posterUrl: basePoster,
    status: "FAILED",
    overview: "A road film with a missing finale."
  },
  {
    tmdbId: "717000",
    title: "Atlas Pilots",
    year: "2024",
    rating: 8.1,
    posterUrl: basePoster,
    status: "MATERIALIZED",
    overview: "Cartographers map a shifting archipelago."
  },
  {
    tmdbId: "392019",
    title: "Helios Run",
    year: "2020",
    rating: 7.0,
    posterUrl: basePoster,
    status: "VIRTUAL",
    overview: "A solar heist under constant daylight."
  },
  {
    tmdbId: "155",
    title: "Midnight Canal",
    year: "2019",
    rating: 7.8,
    posterUrl: basePoster,
    status: "MATERIALIZED",
    overview: "Detectives chase a ghost along the docks."
  }
];

export const mockHomeFeed: HomeFeed = {
  favorites,
  trending,
  updatedAt: now
};

const resourceSet = (statusOverrides?: Partial<ResourceItem>[]): ResourceItem[] => {
  const base: ResourceItem[] = [
    {
      id: "r1",
      name: "4K UHD Master",
      size: "12.4 GB",
      status: "MATERIALIZED",
      updatedAt: "2026-01-06T20:10:00Z",
      webdavPath: "/QuarkMedia/Movies/Signal-Drift/Signal-Drift.4K.mkv"
    },
    {
      id: "r2",
      name: "1080p WebRip",
      size: "6.1 GB",
      status: "VIRTUAL",
      updatedAt: "2026-01-06T19:20:00Z"
    },
    {
      id: "r3",
      name: "720p Compact",
      size: "2.8 GB",
      status: "PROVISIONING",
      updatedAt: "2026-01-06T19:58:00Z"
    },
    {
      id: "r4",
      name: "720p Backup",
      size: "2.6 GB",
      status: "FAILED",
      updatedAt: "2026-01-06T18:40:00Z",
      errorMessage: "Share link expired"
    }
  ];

  if (!statusOverrides) {
    return base;
  }

  return base.map((item, index) => ({
    ...item,
    ...statusOverrides[index]
  }));
};

const detailBase: Omit<TmdbDetail, "tmdbId" | "title"> = {
  overview: "A placeholder synopsis for the upcoming Quark Media release.",
  year: "2024",
  runtime: "128m",
  rating: 8.1,
  genres: ["Sci-Fi", "Thriller"],
  posterUrl: basePoster,
  backdropUrl: baseBackdrop,
  resources: resourceSet()
};

export const mockDetails: Record<string, TmdbDetail> = {
  "872585": {
    tmdbId: "872585",
    title: "Signal Drift",
    ...detailBase,
    resources: resourceSet()
  },
  "114399": {
    tmdbId: "114399",
    title: "Afterglow Harbor",
    ...detailBase,
    year: "2023",
    genres: ["Drama", "Mystery"],
    resources: resourceSet([
      { status: "VIRTUAL" },
      { status: "VIRTUAL" },
      { status: "PROVISIONING" },
      { status: "FAILED" }
    ])
  },
  "603": {
    tmdbId: "603",
    title: "Neon Relay",
    ...detailBase,
    year: "2025",
    genres: ["Action", "Noir"],
    resources: resourceSet([
      { status: "PROVISIONING" },
      { status: "VIRTUAL" },
      { status: "PROVISIONING" },
      { status: "FAILED" }
    ])
  }
};

export const mockQuarkLinks: Record<string, QuarkLink[]> = {
  "872585": [
    {
      id: "q1",
      title: "Signal Drift 4K Pack",
      shareUrl: "https://pan.quark.cn/s/placeholder-1",
      quality: "4K",
      size: "12.4 GB",
      matchScore: 0.92
    },
    {
      id: "q2",
      title: "Signal Drift 1080p",
      shareUrl: "https://pan.quark.cn/s/placeholder-2",
      quality: "1080p",
      size: "6.1 GB",
      matchScore: 0.84
    }
  ],
  "114399": [
    {
      id: "q3",
      title: "Afterglow Harbor Collection",
      shareUrl: "https://pan.quark.cn/s/placeholder-3",
      quality: "1080p",
      size: "5.4 GB",
      matchScore: 0.78
    }
  ]
};

export function getMockDetail(tmdbId: string): TmdbDetail {
  return (
    mockDetails[tmdbId] || {
      tmdbId,
      title: "Untitled Media",
      ...detailBase,
      genres: ["Drama"],
      resources: resourceSet()
    }
  );
}

export function getMockQuarkLinks(tmdbId?: string, query?: string): QuarkLink[] {
  if (tmdbId && mockQuarkLinks[tmdbId]) {
    return mockQuarkLinks[tmdbId];
  }

  if (query) {
    return [
      {
        id: "q-search-1",
        title: `Search result for ${query}`,
        shareUrl: "https://pan.quark.cn/s/search-placeholder",
        quality: "1080p",
        size: "5.9 GB",
        matchScore: 0.71
      }
    ];
  }

  return [];
}