import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedName:
    cleaned_title: Optional[str]
    year: Optional[int]
    episode_info: Optional[str]
    media_type: Optional[str]
    normalized_filename: Optional[str]


def normalize_filename(name: str, folder: Optional[str] = None, ext: Optional[str] = None) -> NormalizedName:
    """
    轻量版文件名规范化：
    - 清洗标题
    - 提取年份
    - 提取剧集信息
    - 生成规范名（如有足够信息）
    """
    base = re.sub(r"[\\/:*?\"<>|]", " ", name)
    cleaned_title = _clean_title(base)
    year = _extract_year(base)
    episode_info = _extract_episode(base)
    media_type = "tv" if episode_info else "movie"

    if not ext:
        m = re.search(r"(\.[A-Za-z0-9]{2,4})$", name)
        ext = m.group(1) if m else ""

    normalized_filename = None
    if cleaned_title:
        if episode_info:
            normalized_filename = f"{cleaned_title}.{episode_info}{ext}"
        elif year:
            normalized_filename = f"{cleaned_title}.{year}{ext}"
        else:
            normalized_filename = f"{cleaned_title}{ext}"

    return NormalizedName(
        cleaned_title=cleaned_title,
        year=year,
        episode_info=episode_info,
        media_type=media_type,
        normalized_filename=normalized_filename,
    )


def _clean_title(text: str) -> str:
    text = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", text)  # 去扩展名
    text = re.sub(r"[\._]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" -.()")
    return text


def _extract_year(text: str) -> Optional[int]:
    m = re.search(r"(20\d{2}|19\d{2})", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _extract_episode(text: str) -> Optional[str]:
    # 支持 SxxEyy / Ep01 / 第xx集 / 01-12
    patterns = [
        (r"S(\d{1,2})E(\d{1,2})", lambda m: f"S{m.group(1).zfill(2)}E{m.group(2).zfill(2)}"),
        (r"EP?(\d{1,2})(?:-EP?(\d{1,2}))?", lambda m: f"S01E{m.group(1).zfill(2)}" + (f"-S01E{m.group(2).zfill(2)}" if m.group(2) else "")),
        (r"第(\d{1,2})集(?:-第?(\d{1,2})集?)?", lambda m: f"S01E{m.group(1).zfill(2)}" + (f"-S01E{m.group(2).zfill(2)}" if m.group(2) else "")),
        (r"^(\d{1,2})(?:-(\d{1,2}))?(?=\D|$)", lambda m: f"S01E{m.group(1).zfill(2)}" + (f"-S01E{m.group(2).zfill(2)}" if m.group(2) else "")),
    ]
    for pattern, formatter in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return formatter(m)
    return None

