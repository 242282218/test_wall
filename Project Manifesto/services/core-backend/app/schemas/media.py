from typing import List, Optional

from pydantic import BaseModel, Field


class MediaItem(BaseModel):
    tmdb_id: str = Field(alias="tmdbId")
    title: str
    year: Optional[str] = None
    rating: Optional[float] = None
    poster_url: Optional[str] = Field(default=None, alias="posterUrl")
    status: str
    overview: Optional[str] = None

    class Config:
        populate_by_name = True


class HomeFeedResponse(BaseModel):
    favorites: List[MediaItem]
    trending: List[MediaItem]
    updated_at: str = Field(alias="updatedAt")

    class Config:
        populate_by_name = True


class MediaResourceItem(BaseModel):
    id: str
    name: str
    size: Optional[str] = None
    status: str
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")
    webdav_path: Optional[str] = Field(default=None, alias="webdavPath")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")

    class Config:
        populate_by_name = True


class MediaDetailResponse(BaseModel):
    tmdb_id: str = Field(alias="tmdbId")
    title: str
    overview: Optional[str] = None
    year: Optional[str] = None
    runtime: Optional[str] = None
    rating: Optional[float] = None
    genres: List[str] = Field(default_factory=list)
    poster_url: Optional[str] = Field(default=None, alias="posterUrl")
    backdrop_url: Optional[str] = Field(default=None, alias="backdropUrl")
    resources: List[MediaResourceItem]

    class Config:
        populate_by_name = True


class SaveVirtualLinkRequest(BaseModel):
    tmdb_id: str = Field(alias="tmdbId")
    link_id: str = Field(alias="linkId")
    title: str
    share_url: str = Field(alias="shareUrl")

    class Config:
        populate_by_name = True


class SaveVirtualLinkResponse(BaseModel):
    status: str
    saved_at: str = Field(alias="savedAt")

    class Config:
        populate_by_name = True


class ProvisionRequest(BaseModel):
    tmdb_id: str = Field(alias="tmdbId")
    link_id: Optional[str] = Field(default=None, alias="linkId")
    share_url: Optional[str] = Field(default=None, alias="shareUrl")

    class Config:
        populate_by_name = True


class TaskRecordResponse(BaseModel):
    task_id: str = Field(alias="taskId")
    status: str
    tmdb_id: str = Field(alias="tmdbId")
    link_id: Optional[str] = Field(default=None, alias="linkId")
    updated_at: str = Field(alias="updatedAt")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")
    progress: Optional[float] = None
    result_webdav_url: Optional[str] = Field(default=None, alias="resultWebdavUrl")

    class Config:
        populate_by_name = True
