import logging
import os
import re
from typing import Optional
from urllib.parse import quote


logger = logging.getLogger("media_classifier")


class MediaType:
    MOVIES = "Movies"
    SERIES = "Series"
    DOCUMENTARIES = "Documentaries"
    ANIME = "Anime"
    MUSIC = "Music"
    OTHERS = "Others"


class MediaClassifier:
    def __init__(self, dest_pattern: Optional[str] = None):
        self.dest_pattern = dest_pattern or os.getenv(
            "TRANSFER_DEST_DIR_PATTERN",
            "/QuarkMedia/{type}/{year}/{title}({year})"
        )
        self._dir_cache = {}

    def classify(self, title: str, filename: Optional[str] = None) -> str:
        title = title or ""
        filename = filename or ""
        combined = f"{title} {filename}".lower()
        
        if self._is_documentary(combined):
            return MediaType.DOCUMENTARIES
        elif self._is_anime(combined):
            return MediaType.ANIME
        elif self._is_series(combined):
            return MediaType.SERIES
        elif self._is_music(combined):
            return MediaType.MUSIC
        else:
            return MediaType.MOVIES

    def _is_documentary(self, text: str) -> bool:
        keywords = ["纪录片", "documentary", "docu"]
        return any(keyword in text for keyword in keywords)

    def _is_anime(self, text: str) -> bool:
        keywords = ["动漫", "anime", "动画", "cartoon", "番剧"]
        return any(keyword in text for keyword in keywords)

    def _is_series(self, text: str) -> bool:
        patterns = [
            r".*s\d+e\d+.*",
            r".*第\d+集.*",
            r".*ep\d+.*",
            r".*season\s*\d+.*",
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    def _is_music(self, text: str) -> bool:
        keywords = ["音乐", "music", "歌曲", "album", "soundtrack"]
        return any(keyword in text for keyword in keywords)

    def extract_year(self, title: str) -> Optional[int]:
        year_match = re.search(r"\b(19|20)\d{2}\b", title)
        if year_match:
            return int(year_match.group())
        return None

    def clean_title(self, title: str) -> str:
        title = title.strip()
        title = re.sub(r"\[.*?\]", "", title)
        title = re.sub(r"\(.*?\)", "", title)
        title = re.sub(r"\{.*?\}", "", title)
        title = re.sub(r"【.*?】", "", title)
        title = re.sub(r"<.*?>", "", title)
        title = re.sub(r"\s+", " ", title)
        title = re.sub(r"[\\/:*?\"<>|]", "_", title)
        return title.strip()

    def build_dest_path(
        self,
        title: str,
        filename: str,
        media_type: Optional[str] = None,
        year: Optional[int] = None,
    ) -> str:
        media_type = media_type or self.classify(title, filename)
        year = year or self.extract_year(title)
        clean_title = self.clean_title(title)
        
        safe_title = quote(clean_title, safe="")
        safe_filename = quote(filename, safe="") if filename else ""
        
        path = self.dest_pattern.format(
            type=media_type,
            year=year or "Unknown",
            title=safe_title,
            filename=safe_filename,
        )
        
        return path

    def get_cached_dir_fid(self, path: str) -> Optional[str]:
        return self._dir_cache.get(path)

    def cache_dir_fid(self, path: str, fid: str) -> None:
        self._dir_cache[path] = fid
        logger.debug("cached directory fid: %s -> %s", path, fid)