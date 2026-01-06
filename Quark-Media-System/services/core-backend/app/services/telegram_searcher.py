import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup


logger = logging.getLogger("telegram_searcher")


CLOUD_PATTERNS = {
    "baiduPan": re.compile(r"https?://(?:pan|yun)\.baidu\.com/[^\s<>\"]+"),
    "tianyi": re.compile(r"https?://cloud\.189\.cn/[^\s<>\"]+"),
    "aliyun": re.compile(r"https?://\w+\.(?:alipan|aliyundrive)\.com/[^\s<>\"]+"),
    "pan115": re.compile(r"https?://(?:115|anxia|115cdn)\.com/s/[^\s<>\"]+"),
    "pan123": re.compile(r"https?://(?:www\.)?123[^/\s<>\"]+\.com/s/[^\s<>\"]+"),
    "quark": re.compile(r"https?://pan\.quark\.cn/[^\s<>\"]+"),
    "yidong": re.compile(r"https?://caiyun\.139\.com/[^\s<>\"]+"),
}
ALLOWED_CLOUD_TYPES = {"quark"}


@dataclass(frozen=True)
class TeleChannel:
    id: str
    name: str


def _get_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_channels() -> List[TeleChannel]:
    channels_raw: Optional[Iterable[Dict[str, Any]]] = None
    env_channels = os.getenv("TELE_CHANNELS", "").strip()
    if env_channels:
        try:
            channels_raw = json.loads(env_channels)
        except json.JSONDecodeError:
            logger.warning("TELE_CHANNELS is not valid JSON, ignoring")

    if channels_raw is None:
        default_path = _get_app_root() / "data" / "tele_channels.json"
        file_path = os.getenv("TELE_CHANNELS_FILE", "").strip()
        candidate = Path(file_path) if file_path else default_path
        if not candidate.is_file() and file_path:
            alt_candidate = _get_app_root() / file_path
            if alt_candidate.is_file():
                candidate = alt_candidate
        if candidate.is_file():
            try:
                channels_raw = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("failed to load channels from %s", candidate)

    if not channels_raw:
        return []

    channels: List[TeleChannel] = []
    for item in channels_raw:
        if not isinstance(item, dict):
            continue
        channel_id = (item.get("id") or "").strip()
        name = (item.get("name") or "").strip()
        if channel_id and name:
            channels.append(TeleChannel(id=channel_id, name=name))
    return channels


def get_channels() -> List[Dict[str, str]]:
    return [{"id": channel.id, "name": channel.name} for channel in _load_channels()]


def _extract_cloud_links(text: str) -> Tuple[List[str], str]:
    links: List[str] = []
    cloud_type = ""
    for name, pattern in CLOUD_PATTERNS.items():
        matches = pattern.findall(text)
        if not matches:
            continue
        if name not in ALLOWED_CLOUD_TYPES:
            continue
        links.extend(matches)
        if not cloud_type:
            cloud_type = name
    deduped = list(dict.fromkeys(links))
    return deduped, cloud_type


class TelegramSearcher:
    def __init__(
        self,
        base_url: Optional[str] = None,
        concurrency: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.base_url = base_url or os.getenv("TELEGRAM_BASE_URL", "https://t.me/s")
        self.concurrency = concurrency or int(os.getenv("TELEGRAM_SEARCH_CONCURRENCY", "6"))
        self.timeout = timeout or float(os.getenv("TELEGRAM_HTTP_TIMEOUT", "20"))
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
                "cache-control": "max-age=0",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def search_all(
        self,
        keyword: str,
        channel_id: Optional[str] = None,
        last_message_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        channels = _load_channels()
        if channel_id:
            channels = [ch for ch in channels if ch.id == channel_id]

        semaphore = asyncio.Semaphore(max(1, self.concurrency))
        results: List[Dict[str, Any]] = []

        async def run_search(channel: TeleChannel) -> None:
            async with semaphore:
                try:
                    items, channel_logo = await self.search_in_web(
                        channel_id=channel.id,
                        keyword=keyword,
                        last_message_id=last_message_id,
                    )
                    if not items:
                        return
                    channel_items = [
                        {
                            **item,
                            "channel": channel.name,
                            "channelId": channel.id,
                        }
                        for item in items
                        if item.get("cloudLinks")
                    ]
                    if channel_items:
                        results.append(
                            {
                                "list": channel_items,
                                "channelInfo": {
                                    "id": channel.id,
                                    "channelId": channel.id,
                                    "name": channel.name,
                                    "channelLogo": channel_logo,
                                },
                                "id": channel.id,
                            }
                        )
                except Exception as exc:
                    logger.error("search channel failed: %s (%s)", channel.name, exc)

        await asyncio.gather(*(run_search(channel) for channel in channels))
        return results

    async def search_in_web(
        self,
        channel_id: str,
        keyword: str,
        last_message_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        params: Dict[str, str] = {}
        if keyword:
            params["q"] = keyword
        if last_message_id:
            params["before"] = last_message_id

        response = await self._client.get(f"/{channel_id}", params=params)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        channel_logo = ""
        header_img = soup.select_one(".tgme_header_link img")
        if header_img and header_img.get("src"):
            channel_logo = header_img["src"]
        else:
            page_photo = soup.select_one(".tgme_page_photo_image img")
            if page_photo and page_photo.get("src"):
                channel_logo = page_photo["src"]

        items: List[Dict[str, Any]] = []
        for wrap in soup.select(".tgme_widget_message_wrap"):
            message_el = wrap.select_one(".tgme_widget_message")
            post_id = message_el.get("data-post") if message_el else ""
            message_id = post_id.split("/", 1)[1] if post_id and "/" in post_id else None

            text_el = wrap.select_one(".js-message_text") or wrap.select_one(".tgme_widget_message_text")
            raw_html = text_el.decode_contents() if text_el else ""
            title_html = raw_html.split("<br")[0] if raw_html else ""
            title = BeautifulSoup(title_html, "html.parser").get_text().strip() if title_html else ""
            content_html = raw_html.replace(title_html, "", 1) if raw_html else ""
            content_html = content_html.split("<a")[0] if content_html else ""
            content = BeautifulSoup(content_html, "html.parser").get_text(" ", strip=True)

            pub_date = None
            time_el = wrap.select_one("time")
            if time_el:
                pub_date = time_el.get("datetime")

            image = None
            photo_el = wrap.select_one(".tgme_widget_message_photo_wrap")
            if photo_el and photo_el.get("style"):
                match = re.search(r"url\\('(.+?)'\\)", photo_el["style"])
                if match:
                    image = match.group(1)

            tags: List[str] = []
            links: List[str] = []
            if text_el:
                for anchor in text_el.select("a"):
                    href = anchor.get("href")
                    if href:
                        links.append(href)
                    text = anchor.get_text(strip=True)
                    if text.startswith("#"):
                        tags.append(text)

            cloud_links, cloud_type = _extract_cloud_links(" ".join(links))
            items.insert(
                0,
                {
                    "id": message_id,
                    "messageId": message_id,
                    "title": title,
                    "content": content,
                    "pubDate": pub_date,
                    "image": image,
                    "cloudLinks": cloud_links,
                    "cloudType": cloud_type,
                    "tags": tags,
                },
            )

        return items, channel_logo


searcher = TelegramSearcher()
