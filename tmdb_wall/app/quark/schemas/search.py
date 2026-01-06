from typing import Optional, List
from pydantic import BaseModel, Field


class SearchByTmdbIdRequest(BaseModel):
    tmdb_id: int
    media_type: Optional[str] = None  # 可选：movie 或 tv，如果不提供则自动检测
    max_results: Optional[int] = 10
    deduplicate: Optional[bool] = True


class SearchByTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    year: Optional[int] = Field(None, ge=1850, le=2100)
    max_results: Optional[int] = 10
    deduplicate: Optional[bool] = True


class ResourceDto(BaseModel):
    name: str
    normalized_name: Optional[str] = None
    link: str
    confidence: Optional[float] = None
    quality_score: Optional[float] = None
    overall_score: Optional[float] = None
    quality_level: Optional[str] = None
    resolution: Optional[str] = None
    codec: Optional[str] = None
    quality_tags: Optional[List[str]] = None
    is_best: Optional[bool] = None


class MediaDto(BaseModel):
    tmdb_id: Optional[int] = None
    title: Optional[str] = None
    original_title: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    media_type: Optional[str] = None


class SearchResponse(BaseModel):
    success: bool
    media: Optional[MediaDto] = None
    resources: List[ResourceDto] = []
    total: int = 0
    query_time: Optional[float] = None
    message: Optional[str] = None

