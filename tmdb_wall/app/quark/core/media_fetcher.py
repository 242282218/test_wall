import time

import requests

from app.config import get_settings
from app.quark.core.models import MediaInfo
from app.quark.logger import logger

settings = get_settings()


class MediaFetcher:
    """精简版 TMDB 获取器"""

    def __init__(self, api_key: str | None = None, max_retries: int = 2, retry_delay: float = 0.5):
        self.api_key = api_key or settings.tmdb_api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.language = "zh-CN"
        self.max_retries = max(1, max_retries)
        self.retry_delay = max(0.0, retry_delay)

    def _get(self, path: str, params: dict) -> dict | None:
        if not self.api_key:
            return None
        url = f"{self.base_url}{path}"
        params = {**params, "api_key": self.api_key, "language": self.language}
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                logger.warning(
                    f"TMDB request failed (attempt {attempt + 1}/{self.max_retries}): {exc}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                return None
            except ValueError as exc:
                logger.warning(f"TMDB response parse failed: {exc}")
                return None
        return None

    def fetch_by_tmdb_id(self, tmdb_id: int, media_type: str = "movie") -> MediaInfo | None:
        data = self._get(f"/{media_type}/{tmdb_id}", {})
        if not data:
            return None
        return self._to_media_info(data, media_type)

    def search_by_title(self, title: str, year: int | None = None, media_type: str = "multi") -> MediaInfo | None:
        data = self._get(f"/search/{media_type}", {"query": title, "year": year} if year else {"query": title})
        if not data or not data.get("results"):
            return None
        best = data["results"][0]
        mt = best.get("media_type") or ("tv" if "name" in best else "movie")
        return self._to_media_info(best, mt)

    def _to_media_info(self, d: dict, media_type: str) -> MediaInfo:
        year_str = (d.get("release_date") or d.get("first_air_date") or "0000")[:4]
        try:
            year = int(year_str) if year_str.isdigit() else None
        except (ValueError, AttributeError):
            year = None
            
        return MediaInfo(
            tmdb_id=d.get("id"),
            title=d.get("title") or d.get("name") or "",
            original_title=d.get("original_title") or d.get("original_name") or "",
            year=year,
            rating=d.get("vote_average"),
            overview=d.get("overview") or "",
            poster_path=d.get("poster_path"),
            backdrop_path=d.get("backdrop_path"),
            media_type=media_type,
        )

