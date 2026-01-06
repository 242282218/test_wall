"""
Quark share link parser.

This module reverse engineers the Quark web API to fetch the full directory
tree for a share link. It handles token acquisition (stoken), pagination,
recursive traversal, and retry logic for network robustness.
"""

from __future__ import annotations

import time
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential


class QuarkShareError(Exception):
    """Base exception for share parsing failures."""


class QuarkShareAuthError(QuarkShareError):
    """Raised when the share link requires or rejects a passcode."""


class QuarkShareNotFoundError(QuarkShareError):
    """Raised when the share link is invalid or expired."""


class QuarkShareNetworkError(QuarkShareError):
    """Raised for transient network errors."""


@dataclass(frozen=True)
class ShareContext:
    """Resolved share context for subsequent list calls."""
    share_code: str
    passcode: str
    stoken: str


class QuarkShareParser:
    """
    Parser that resolves a Quark share URL into a full file tree.

    Usage:
        parser = QuarkShareParser(cookie="...")
        files = await parser.parse_share_link("https://pan.quark.cn/s/xxxxx?pwd=abcd")
    """

    def __init__(
        self,
        base_url: str = "https://drive-h.quark.cn",
        timeout: float = 30.0,
        max_retries: int = 3,
        page_size: int = 200,
        cookie: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.page_size = max(1, min(page_size, 200))
        self._client = httpx.AsyncClient(timeout=self.timeout, headers=self._default_headers())
        if cookie:
            self.set_cookie(cookie)

    async def __aenter__(self) -> "QuarkShareParser":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the internal HTTP client."""
        await self._client.aclose()

    def set_cookie(self, cookie: str) -> None:
        """Set or update the Cookie header for authenticated requests."""
        self._client.headers["cookie"] = cookie

    async def parse_share_link(self, share_url: str) -> List[Dict]:
        """
        Parse a share URL and return a flattened list of all files and folders.

        Output nodes include: fid, name, parent_fid, is_dir, path, size, token.
        """
        share_code, passcode = self._extract_share_info(share_url)
        stoken = await self._fetch_share_token(share_code, passcode)
        context = ShareContext(share_code=share_code, passcode=passcode, stoken=stoken)

        results: List[Dict] = []
        await self._walk_share_tree(context, results)
        return results

    def _default_headers(self) -> Dict[str, str]:
        """Headers mirroring the Quark web client."""
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "content-type": "application/json",
            "origin": "https://pan.quark.cn",
            "referer": "https://pan.quark.cn/",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

    def _extract_share_info(self, share_url: str) -> Tuple[str, str]:
        """
        Extract share_code and passcode from a Quark share URL.

        Supports:
        - https://pan.quark.cn/s/<code>?pwd=xxxx
        - Raw share_code only
        """
        share_url = share_url.strip()
        if not share_url:
            raise QuarkShareError("share_url is empty")

        # Raw share code fallback.
        if "://" not in share_url and "/" not in share_url:
            return share_url, ""

        parsed = urlparse(share_url)
        match = re.search(r"/s/([A-Za-z0-9]+)", parsed.path)
        if not match:
            raise QuarkShareError(f"Unable to parse share code from: {share_url}")

        share_code = match.group(1)
        query = parse_qs(parsed.query)
        passcode = (
            (query.get("pwd") or query.get("passcode") or query.get("password") or query.get("p") or [""])[0]
        )
        return share_code, passcode

    async def _fetch_share_token(self, share_code: str, passcode: str) -> str:
        """
        Exchange share_code + passcode for stoken, required by list APIs.
        """
        endpoint = "/1/clouddrive/share/sharepage/token"
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "__dt": "994",
            "__t": self._now_ms(),
        }
        payload = {"pwd_id": share_code, "passcode": passcode}

        data = await self._request("POST", endpoint, params=params, json=payload)
        if data.get("status") != 200 or not data.get("data"):
            message = data.get("message") or data.get("error") or "share token failed"
            if "passcode" in str(message).lower() or "密码" in str(message):
                raise QuarkShareAuthError(message)
            raise QuarkShareNotFoundError(message)

        stoken = data["data"].get("stoken")
        if not stoken:
            raise QuarkShareAuthError("missing stoken, passcode may be required")
        return stoken

    async def _walk_share_tree(self, context: ShareContext, results: List[Dict]) -> None:
        """
        Depth-first traversal over the share file tree.
        """
        stack: List[Tuple[str, str]] = [("0", "/")]
        while stack:
            pdir_fid, parent_path = stack.pop()
            async for items in self._iter_share_list(context, pdir_fid):
                for item in items:
                    node = self._build_node(item, pdir_fid, parent_path)
                    results.append(node)

                    if node["is_dir"]:
                        stack.append((node["fid"], node["path"]))

    async def _iter_share_list(self, context: ShareContext, pdir_fid: str):
        """
        Async generator that yields pages of items for a given directory.
        """
        page = 1
        size = self.page_size
        while True:
            items, total = await self._list_share_dir(context, pdir_fid, page, size)
            if not items:
                break
            yield items

            if total is not None:
                if page * size >= total:
                    break
            elif len(items) < size:
                break
            page += 1

    async def _list_share_dir(
        self,
        context: ShareContext,
        pdir_fid: str,
        page: int,
        size: int,
    ) -> Tuple[List[Dict], Optional[int]]:
        """
        List a single page of a directory within the share.
        """
        endpoint = "/1/clouddrive/share/sharepage/detail"
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "pwd_id": context.share_code,
            "stoken": context.stoken,
            "pdir_fid": pdir_fid,
            "force": "0",
            "_page": str(page),
            "_size": str(size),
            "_fetch_banner": "0",
            "_fetch_share": "1",
            "_fetch_total": "1",
            "_sort": "file_type:asc,updated_at:desc",
            "__dt": "1589",
            "__t": self._now_ms(),
        }

        data = await self._request("GET", endpoint, params=params)
        payload = data.get("data") or {}
        items = payload.get("list") or []

        total = self._extract_total(data, payload)
        return items, total

    def _build_node(self, item: Dict, parent_fid: str, parent_path: str) -> Dict:
        """
        Normalize an item into a standard JSON node structure.
        """
        fid = item.get("fid") or ""
        name = item.get("file_name") or ""
        is_dir = bool(item.get("dir")) or item.get("file_type") == 0
        path = self._join_path(parent_path, name)
        return {
            "fid": fid,
            "name": name,
            "is_dir": is_dir,
            "parent_fid": parent_fid,
            "path": path,
            "size": item.get("size"),
            "file_type": item.get("file_type"),
            "share_fid_token": item.get("share_fid_token"),
        }

    def _extract_total(self, data: Dict, payload: Dict) -> Optional[int]:
        """
        Best-effort extraction of total count from varied response shapes.
        """
        for container in (payload, data.get("metadata") or {}, payload.get("metadata") or {}):
            for key in ("_total", "total", "_count", "count"):
                if key in container and isinstance(container[key], int):
                    return container[key]
        return None

    def _join_path(self, parent_path: str, name: str) -> str:
        """Join parent and child into a normalized Unix-style path."""
        if parent_path == "/":
            return f"/{name}"
        return f"{parent_path}/{name}"

    def _now_ms(self) -> int:
        """Current timestamp in milliseconds."""
        return int(time.time() * 1000)

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        HTTP request wrapper with retry and structured error handling.
        """
        url = f"{self.base_url}{endpoint}"
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(QuarkShareNetworkError),
            reraise=True,
        )

        async for attempt in retrying:
            with attempt:
                try:
                    response = await self._client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    # 4xx/5xx from API; treat as non-retry unless network-related.
                    raise QuarkShareError(
                        f"HTTP {exc.response.status_code} for {url}"
                    ) from exc
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    raise QuarkShareNetworkError(str(exc)) from exc
                except ValueError as exc:
                    # JSON decode error or unexpected response format.
                    raise QuarkShareError("Invalid JSON response") from exc
