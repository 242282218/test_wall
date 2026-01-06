from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv 未安装，跳过
except Exception:
    pass  # 加载失败，跳过


class Settings(BaseSettings):
    """应用配置，来自环境变量或 .env 文件。"""

    # TMDB 配置（原有）
    tmdb_api_key: str = Field(..., alias="TMDB_API_KEY")
    default_language: str = Field("zh-CN", alias="DEFAULT_LANG")
    tmdb_api_base: str = Field("https://api.themoviedb.org/3", alias="TMDB_API_BASE")
    tmdb_image_base: str = Field("https://image.tmdb.org/t/p/", alias="TMDB_IMAGE_BASE")

    # 夸克搜索配置（新增）
    quark_search_api_prefix: str = Field("/api/quark", alias="QUARK_SEARCH_API_PREFIX")
    quark_search_database_url: str = Field("sqlite:///./data/quark_search.db", alias="QUARK_SEARCH_DATABASE_URL")
    quark_search_base_url: str = Field("https://b.funletu.com", alias="QUARK_SEARCH_BASE_URL")
    quark_search_rate_limit: float = Field(0.5, alias="QUARK_SEARCH_RATE_LIMIT")
    quark_search_timeout: int = Field(10, alias="QUARK_SEARCH_TIMEOUT")
    quark_search_max_retries: int = Field(3, alias="QUARK_SEARCH_MAX_RETRIES")
    quark_search_confidence_threshold: float = Field(
        0.5, ge=0.0, le=1.0, alias="QUARK_SEARCH_CONFIDENCE_THRESHOLD"
    )
    quark_search_confidence_weight: float = Field(
        0.7, ge=0.0, le=1.0, alias="QUARK_SEARCH_CONFIDENCE_WEIGHT"
    )
    quark_search_quality_weight: float = Field(
        0.3, ge=0.0, le=1.0, alias="QUARK_SEARCH_QUALITY_WEIGHT"
    )
    quark_search_similarity_band: float = Field(0.06, alias="QUARK_SEARCH_SIMILARITY_BAND")
    quark_search_max_results: int = Field(50, alias="QUARK_SEARCH_MAX_RESULTS")
    quark_search_enable_rename: bool = Field(False, alias="QUARK_SEARCH_ENABLE_RENAME")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

