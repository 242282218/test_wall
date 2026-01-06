from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from .config import get_settings

DEFAULT_POSTER_SIZE = "w500"
DEFAULT_BACKDROP_SIZE = "w780"
DEFAULT_LANG = "zh-CN"

# 简单的类型到视觉风格映射，用于 CSS tone
GENRE_TONE = {
    10749: "romance",  # 爱情
    18: "family",  # 剧情/亲情
    10751: "family",
    28: "action",  # 动作
    80: "action",
    9648: "mystery",  # 悬疑
    53: "mystery",
    27: "mystery",
    878: "scifi",  # 科幻
    14: "scifi",
}


class TmdbClient:
    def __init__(
        self,
        api_key: str,
        *,
        api_base: Optional[str] = None,
        image_base: Optional[str] = None,
        language: str = DEFAULT_LANG,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key
        self.api_base = api_base or settings.tmdb_api_base
        self.image_base = image_base or settings.tmdb_image_base
        self.language = language or settings.default_language
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={"Accept": "application/json"},
            timeout=10.0,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30.0,
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        params.setdefault("api_key", self.api_key)
        params.setdefault("language", self.language)
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def trending(self, media_type: str = "all", window: str = "week") -> List[Dict[str, Any]]:
        data = await self._get(f"/trending/{media_type}/{window}")
        return data.get("results", [])

    async def movies(self, category: str = "popular") -> List[Dict[str, Any]]:
        data = await self._get(f"/movie/{category}")
        return data.get("results", [])

    async def tv(self, category: str = "popular") -> List[Dict[str, Any]]:
        data = await self._get(f"/tv/{category}")
        return data.get("results", [])

    async def search_multi(self, query: str) -> List[Dict[str, Any]]:
        if not query:
            return []
        data = await self._get("/search/multi", params={"query": query, "include_adult": "false"})
        return data.get("results", [])

    async def search(self, query: str, media_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if not query:
            return []
        params = {"query": query, "include_adult": "false"}
        if media_type == "movie":
            data = await self._get("/search/movie", params=params)
        elif media_type == "tv":
            data = await self._get("/search/tv", params=params)
        else:
            data = await self._get("/search/multi", params=params)
        return data.get("results", [])

    async def details(
        self, media_type: str, item_id: int, language_override: Optional[str] = None
    ) -> Dict[str, Any]:
        # 拉取包含视频、图片、演职员、相关推荐
        params: Dict[str, Any] = {
            "append_to_response": "videos,images,credits,recommendations,similar",
            # 带上多语言，避免视频/图片因语言缺失
            "include_image_language": "zh,null,en",
            "include_video_language": "zh,en,null",
        }
        if language_override:
            params["language"] = language_override
        return await self._get(f"/{media_type}/{item_id}", params=params)

    async def person(
        self, person_id: int, language_override: Optional[str] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "append_to_response": "combined_credits,images,external_ids",
            "include_image_language": "zh,null,en",
        }
        if language_override:
            params["language"] = language_override
        return await self._get(f"/person/{person_id}", params=params)

    def image_url(self, path: Optional[str], size: str = DEFAULT_POSTER_SIZE) -> Optional[str]:
        if not path:
            return None
        return f"{self.image_base}{size}{path}"


def tone_from_genres(genre_ids: Optional[List[int]]) -> str:
    if not genre_ids:
        return "neutral"
    for gid in genre_ids:
        if gid in GENRE_TONE:
            return GENRE_TONE[gid]
    return "neutral"


def adapt_poster(item: Dict[str, Any], client: TmdbClient) -> Dict[str, Any]:
    media_type = item.get("media_type") or ("movie" if "title" in item else "tv")
    title = item.get("title") or item.get("name") or "未命名"
    date_field = item.get("release_date") or item.get("first_air_date") or ""
    year = date_field.split("-")[0] if date_field else ""
    vote = item.get("vote_average")

    def _format_rating(value: Any) -> str:
        try:
            return f"{float(value):.1f}"
        except (TypeError, ValueError):
            return "--"

    tmdb_score = _format_rating(vote)
    card_text = f"{year or '--'} · TMDB {tmdb_score}"

    poster_path = item.get("poster_path") or item.get("backdrop_path")
    backdrop_path = item.get("backdrop_path") or item.get("poster_path")

    return {
        "id": item.get("id"),
        "media_type": media_type,
        "title": card_text,
        "display_title": title,
        "subtitle": "",
        "card_text": card_text,
        "year": year,
        "tmdb_rating": tmdb_score,
        "overview": item.get("overview") or "",
        "genres": item.get("genre_ids") or [],
        "tone": tone_from_genres(item.get("genre_ids")),
        "poster_url": client.image_url(poster_path, DEFAULT_POSTER_SIZE),
        "backdrop_url": client.image_url(backdrop_path, DEFAULT_BACKDROP_SIZE),
    }


async def gather_sections(client: TmdbClient) -> Dict[str, List[Dict[str, Any]]]:
    trending, popular, top_rated, now_playing = await asyncio.gather(
        client.trending("all", "week"),
        client.movies("popular"),
        client.movies("top_rated"),
        client.movies("now_playing"),
    )
    return {
        "trending": trending,
        "popular": popular,
        "top_rated": top_rated,
        "now_playing": now_playing,
    }

