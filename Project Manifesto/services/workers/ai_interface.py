from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel


class MediaCategory(str, Enum):
    MOVIES = "Movies"
    SERIES = "Series"
    DOCUMENTARIES = "Documentaries"
    ANIME = "Anime"
    MUSIC = "Music"
    OTHERS = "Others"


class ClassificationResult(BaseModel):
    category: MediaCategory
    confidence: float
    metadata: Dict[str, Any] = {}


class TagSuggestion(BaseModel):
    tag: str
    confidence: float


class MediaMetadata(BaseModel):
    title: str
    year: Optional[int] = None
    genre: List[str] = []
    tags: List[str] = []
    description: Optional[str] = None
    language: Optional[str] = None
    rating: Optional[float] = None
    duration: Optional[int] = None


class AIClassifier(ABC):
    @abstractmethod
    async def classify_media(
        self,
        title: str,
        filename: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        pass

    @abstractmethod
    async def extract_metadata(
        self,
        title: str,
        filename: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> MediaMetadata:
        pass

    @abstractmethod
    async def suggest_tags(
        self,
        title: str,
        description: Optional[str] = None,
        limit: int = 10
    ) -> List[TagSuggestion]:
        pass


class AIEnhancer(ABC):
    @abstractmethod
    async def enhance_description(
        self,
        title: str,
        original_description: Optional[str] = None,
        metadata: Optional[MediaMetadata] = None
    ) -> str:
        pass

    @abstractmethod
    async def generate_summary(
        self,
        title: str,
        metadata: Optional[MediaMetadata] = None
    ) -> str:
        pass

    @abstractmethod
    async def detect_duplicate(
        self,
        title: str,
        existing_titles: List[str],
        threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        pass


class AIService(ABC):
    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass
