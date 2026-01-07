import re
import logging
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher

from .ai_interface import (
    AIClassifier,
    AIEnhancer,
    AIService,
    ClassificationResult,
    MediaCategory,
    MediaMetadata,
    TagSuggestion
)


logger = logging.getLogger(__name__)


class RuleBasedClassifier(AIClassifier):
    def __init__(self):
        self._category_patterns = {
            MediaCategory.MOVIES: [
                r'\b(movie|film|电影|影片)\b',
                r'\b\d{4}\s*\(.*\)',  # Year (Country) format
                r'\b(1080p|720p|4K|BluRay|WEB-DL)\b'
            ],
            MediaCategory.SERIES: [
                r'\b(S\d+E\d+|Season\s*\d+|Episode\s*\d+|第\d+季|第\d+集)\b',
                r'\b(TV|Series|剧集|连续剧)\b',
                r'\b(Complete|全集|完结)\b'
            ],
            MediaCategory.DOCUMENTARIES: [
                r'\b(documentary|纪录片)\b',
                r'\b(National Geographic|Discovery|BBC)\b',
                r'\b(探索|纪实)\b'
            ],
            MediaCategory.ANIME: [
                r'\b(anime|animation|动漫|动画)\b',
                r'\b(番剧|日漫)\b',
                r'\b(ova|oad|ova)\b'
            ],
            MediaCategory.MUSIC: [
                r'\b(music|song|album|音乐|歌曲|专辑)\b',
                r'\.(mp3|flac|wav|aac|m4a)$',
                r'\b(soundtrack|ost|原声)\b'
            ]
        }

        self._genre_patterns = {
            'Action': r'\b(action|动作)\b',
            'Comedy': r'\b(comedy|喜剧)\b',
            'Drama': r'\b(drama|剧情)\b',
            'Horror': r'\b(horror|恐怖)\b',
            'Sci-Fi': r'\b(scifi|sci-fi|科幻)\b',
            'Thriller': r'\b(thriller|惊悚)\b',
            'Romance': r'\b(romance|爱情)\b',
            'Adventure': r'\b(adventure|冒险)\b',
            'Fantasy': r'\b(fantasy|奇幻)\b',
            'Crime': r'\b(crime|犯罪)\b'
        }

    async def classify_media(
        self,
        title: str,
        filename: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        text = f"{title} {filename or ''}".lower()
        
        scores = {}
        for category, patterns in self._category_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text, re.IGNORECASE))
                score += matches
            scores[category] = score
        
        max_score = max(scores.values())
        if max_score == 0:
            category = MediaCategory.OTHERS
            confidence = 0.5
        else:
            category = max(scores, key=scores.get)
            confidence = min(max_score / 3.0, 1.0)
        
        metadata = {
            "matched_patterns": scores,
            "text_length": len(text)
        }
        
        return ClassificationResult(
            category=category,
            confidence=confidence,
            metadata=metadata
        )

    async def extract_metadata(
        self,
        title: str,
        filename: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> MediaMetadata:
        text = f"{title} {filename or ''}"
        
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        year = int(year_match.group()) if year_match else None
        
        genres = []
        for genre, pattern in self._genre_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                genres.append(genre)
        
        language = self._detect_language(text)
        
        return MediaMetadata(
            title=title,
            year=year,
            genre=genres,
            tags=[],
            description=None,
            language=language,
            rating=None,
            duration=None
        )

    async def suggest_tags(
        self,
        title: str,
        description: Optional[str] = None,
        limit: int = 10
    ) -> List[TagSuggestion]:
        text = f"{title} {description or ''}".lower()
        
        tags = []
        all_patterns = {
            **self._genre_patterns,
            'HD': r'\b(1080p|720p|4k|hd)\b',
            'Subtitles': r'\b(sub|subtitle|字幕)\b',
            'Dual Audio': r'\b(dual|双语)\b',
            'Complete': r'\b(complete|全集|完结)\b'
        }
        
        for tag, pattern in all_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                tags.append(TagSuggestion(tag=tag, confidence=0.9))
        
        return tags[:limit]

    def _detect_language(self, text: str) -> Optional[str]:
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if chinese_chars > english_chars:
            return "zh-CN"
        elif english_chars > chinese_chars:
            return "en-US"
        else:
            return None


class RuleBasedEnhancer(AIEnhancer):
    async def enhance_description(
        self,
        title: str,
        original_description: Optional[str] = None,
        metadata: Optional[MediaMetadata] = None
    ) -> str:
        if original_description:
            return original_description
        
        parts = [title]
        
        if metadata:
            if metadata.year:
                parts.append(f"({metadata.year})")
            if metadata.genre:
                parts.append(f"类型: {', '.join(metadata.genre)}")
        
        return " | ".join(parts) if parts else title

    async def generate_summary(
        self,
        title: str,
        metadata: Optional[MediaMetadata] = None
    ) -> str:
        summary = f"媒体文件: {title}"
        
        if metadata:
            if metadata.year:
                summary += f"\n年份: {metadata.year}"
            if metadata.genre:
                summary += f"\n类型: {', '.join(metadata.genre)}"
            if metadata.tags:
                summary += f"\n标签: {', '.join(metadata.tags)}"
        
        return summary

    async def detect_duplicate(
        self,
        title: str,
        existing_titles: List[str],
        threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        duplicates = []
        
        for existing_title in existing_titles:
            similarity = SequenceMatcher(None, title.lower(), existing_title.lower()).ratio()
            if similarity >= threshold:
                duplicates.append({
                    "title": existing_title,
                    "similarity": similarity
                })
        
        return sorted(duplicates, key=lambda x: x["similarity"], reverse=True)


class AIServiceAdapter(AIService):
    def __init__(
        self,
        classifier: Optional[AIClassifier] = None,
        enhancer: Optional[AIEnhancer] = None
    ):
        self._classifier = classifier or RuleBasedClassifier()
        self._enhancer = enhancer or RuleBasedEnhancer()
        self._initialized = False

    async def initialize(self) -> bool:
        try:
            self._initialized = True
            logger.info("AI服务初始化成功")
            return True
        except Exception as e:
            logger.error(f"AI服务初始化失败: {e}")
            return False

    async def health_check(self) -> bool:
        return self._initialized

    async def shutdown(self) -> None:
        self._initialized = False
        logger.info("AI服务已关闭")

    @property
    def classifier(self) -> AIClassifier:
        return self._classifier

    @property
    def enhancer(self) -> AIEnhancer:
        return self._enhancer
