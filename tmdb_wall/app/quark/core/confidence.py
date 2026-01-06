import re
from difflib import SequenceMatcher
from typing import Set

from app.quark.core.models import MediaInfo, MatchDetails


class ConfidenceCalculator:
    """精简版置信度计算"""

    def __init__(
        self,
        title_weight: float = 0.5,
        year_weight: float = 0.2,
        keyword_weight: float = 0.2,
        metadata_weight: float = 0.1,
        similarity_threshold: float = 0.6,
    ):
        self.title_weight = title_weight
        self.year_weight = year_weight
        self.keyword_weight = keyword_weight
        self.metadata_weight = metadata_weight
        self.similarity_threshold = similarity_threshold

        self.weights = {
            "title": title_weight,
            "year": year_weight,
            "keyword": keyword_weight,
            "metadata": metadata_weight,
        }

    def calculate(self, resource_name: str, media_info: MediaInfo) -> MatchDetails:
        cleaned = self._clean(resource_name)
        title_score = self._title_score(cleaned, media_info)
        year_score = self._year_score(cleaned, media_info)
        keyword_score, matched_keywords = self._keyword_score(cleaned, media_info)
        metadata_score, matched_actors, matched_directors, matched_genres = self._metadata_score(
            cleaned, media_info
        )
        return MatchDetails(
            title_match_score=title_score,
            year_match_score=year_score,
            keyword_match_score=keyword_score,
            metadata_match_score=metadata_score,
            matched_keywords=matched_keywords,
            matched_actors=matched_actors,
            matched_directors=matched_directors,
            matched_genres=matched_genres,
        )

    def _clean(self, text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"[《》\[\]()（）【】{}]", " ", text)
        text = re.sub(r"[|｜/\\]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _title_score(self, resource_name: str, media_info: MediaInfo) -> float:
        best = 0.0
        for title in media_info.get_all_titles():
            score = SequenceMatcher(None, resource_name.lower(), title.lower()).ratio()
            best = max(best, score)
        return min(1.0, best)

    def _year_score(self, resource_name: str, media_info: MediaInfo) -> float:
        if not media_info.year:
            return 0.0
        years = self._extract_years(resource_name)
        if not years:
            return 0.5
        best = 0.0
        for y in years:
            if y == media_info.year:
                best = 1.0
            elif abs(y - media_info.year) <= 1:
                best = max(best, 0.8)
            elif abs(y - media_info.year) <= 2:
                best = max(best, 0.6)
        return best

    def _extract_years(self, text: str) -> Set[int]:
        matches = re.findall(r"(?:19|20)\d{2}", text)
        return {int(m) for m in matches}

    def _keyword_score(self, resource_name: str, media_info: MediaInfo):
        resource_words = self._words(resource_name)
        keywords = media_info.get_keywords()
        matched = set()
        for kw in keywords:
            for w in self._words(kw):
                if w in resource_words:
                    matched.add(w)
        if not keywords:
            return 0.0, matched
        return min(1.0, len(matched) / len(keywords)), matched

    def _metadata_score(self, resource_name: str, media_info: MediaInfo):
        resource_words = self._words(resource_name)
        matched_actors = {a for a in media_info.actors if self._words(a) & resource_words}
        matched_directors = {d for d in media_info.directors if self._words(d) & resource_words}
        matched_genres = {g for g in media_info.genres if self._words(g) & resource_words}
        total = len(media_info.actors) + len(media_info.directors) + len(media_info.genres)
        matched_total = len(matched_actors) + len(matched_directors) + len(matched_genres)
        if total == 0:
            return 0.0, matched_actors, matched_directors, matched_genres
        return min(1.0, matched_total / total), matched_actors, matched_directors, matched_genres

    def _words(self, text: str) -> Set[str]:
        words = set()
        text = re.sub(r"[^\w\u4e00-\u9fff]", " ", text)
        for w in text.split():
            if len(w) >= 2:
                words.add(w.lower())
        return words

