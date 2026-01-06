from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class MatchDetails:
    title_match_score: float = 0.0
    year_match_score: float = 0.0
    keyword_match_score: float = 0.0
    metadata_match_score: float = 0.0
    matched_keywords: Set[str] = field(default_factory=set)
    matched_actors: Set[str] = field(default_factory=set)
    matched_directors: Set[str] = field(default_factory=set)
    matched_genres: Set[str] = field(default_factory=set)

    def get_confidence(self, weights: dict) -> float:
        return (
            self.title_match_score * weights.get("title", 0.0)
            + self.year_match_score * weights.get("year", 0.0)
            + self.keyword_match_score * weights.get("keyword", 0.0)
            + self.metadata_match_score * weights.get("metadata", 0.0)
        )


@dataclass
class QualityInfo:
    level: str = "UNKNOWN"
    resolution: Optional[str] = None
    codec: Optional[str] = None
    bitrate: Optional[str] = None
    file_size: Optional[str] = None
    file_count: Optional[int] = None
    total_size_gb: Optional[float] = None
    hdr_format: Optional[str] = None
    dynamic_range: Optional[str] = None
    dolby_vision: bool = False
    dolby_audio: bool = False

    def get_score(self) -> float:
        # Quality score based on resolution plus HDR/Dolby/codec/size bonuses.
        level_map = {
            "UHD_4K": 0.8,
            "FHD_1080P": 0.6,
            "HD_720P": 0.45,
            "SD_480P": 0.3,
            "LD_360P": 0.2,
            "UNKNOWN": 0.1,
        }
        base = level_map.get(self.level, 0.1)
        bonus = 0.0
        if self.hdr_format:
            bonus += 0.1
            if self.hdr_format == "HDR10+":
                bonus += 0.03
            elif self.hdr_format == "Dolby Vision":
                bonus += 0.05
        if self.dolby_audio:
            bonus += 0.04
        if self.codec in ("HEVC", "AV1"):
            bonus += 0.03
        bonus += self._size_bonus()
        return min(round(base + bonus, 4), 1.0)

    def _size_bonus(self) -> float:
        if not self.total_size_gb:
            return 0.0
        size = self.total_size_gb
        if self.level == "UHD_4K":
            if size >= 20:
                return 0.04
            if size >= 12:
                return 0.02
        if self.level == "FHD_1080P":
            if size >= 8:
                return 0.02
            if size >= 4:
                return 0.01
        if self.level == "HD_720P" and size >= 4:
            return 0.01
        return 0.0

    def get_tags(self) -> List[str]:
        tags: List[str] = []
        if self.resolution and self.resolution != "Unknown":
            tags.append(self.resolution)
        if self.hdr_format:
            if self.hdr_format == "HDR10+":
                tags.append("HDR10+")
            else:
                tags.append("HDR")
        elif self.dynamic_range == "SDR":
            tags.append("SDR")
        if self.dolby_vision or self.dolby_audio:
            tags.append("杜比")
        # Preserve order while de-duplicating.
        return list(dict.fromkeys(tags))


@dataclass
class MediaInfo:
    tmdb_id: Optional[int] = None
    title: Optional[str] = None
    original_title: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    media_type: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)
    directors: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)

    def get_all_titles(self) -> List[str]:
        titles = []
        if self.title:
            titles.append(self.title)
        if self.original_title:
            titles.append(self.original_title)
        titles.extend(self.aliases)
        return [t for t in titles if t]

    def get_keywords(self) -> List[str]:
        # 简化：使用标题和别名作为关键词来源
        return self.get_all_titles()


@dataclass
class MatchResult:
    resource: "QuarkResource"
    media_info: MediaInfo
    confidence: float
    quality_score: float
    overall_score: float
    match_details: MatchDetails
    quality_info: QualityInfo
    is_best: bool = False

