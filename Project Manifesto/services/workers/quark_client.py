import logging
import os
import posixpath
import re
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


logger = logging.getLogger("quark_client")


class QuarkClientError(Exception):
    pass


class QuarkAuthError(QuarkClientError):
    pass


class QuarkNetworkError(QuarkClientError):
    pass


class QuarkAPIError(QuarkClientError):
    pass


class QuarkClient:
    def __init__(self, cookie: str, max_retries: int = 3, timeout: float = 30.0) -> None:
        if not cookie:
            raise ValueError("QUARK_COOKIE is required")
        self.base_url = "https://drive.quark.cn"
        self.share_base_url = "https://drive-h.quark.cn"
        self._share_safe_host_url: Optional[str] = None
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(
            headers={
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
                "cookie": cookie,
            },
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _get_config(self) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}/1/clouddrive/config"
            return await self._request_json("GET", url, params=self._base_params())
        except Exception:
            logger.exception("get_config failed")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((QuarkNetworkError, httpx.TimeoutException)),
        reraise=True
    )
    async def get_stoken(self, share_url: str) -> str:
        logger.info("share_url raw input: %s", share_url)
        share_code, passcode = self._extract_share_info(share_url)
        logger.info("share_code extracted: %s", share_code)
        logger.info("passcode extracted: %s", passcode)

        normalized_url = self._normalize_share_url(share_url, share_code, passcode)
        logger.info("share_url normalized: %s", normalized_url)

        try:
            logger.info("requesting stoken via share token API")
            stoken = await self._get_share_token(share_code, passcode)
            logger.info("stoken obtained via API")
            return stoken
        except QuarkAuthError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.error("share token API network error: %s", exc)
            raise QuarkNetworkError(f"Network error during stoken fetch: {exc}") from exc
        except Exception as exc:
            logger.exception("share token API failed, falling back to HTML parsing")

        try:
            headers = dict(self.client.headers)
            self._log_request("GET", normalized_url, headers, None, None)
            response = await self.client.get(normalized_url)
            status_code = response.status_code
            html = response.text
            logger.info("share page status: %s", status_code)
            logger.info("share page body: %s", html)
            response.raise_for_status()

            patterns = [
                r'"stoken"\s*:\s*"([^"]+)"',
                r"stoken\s*[:=]\s*['\"]([^'\"]+)['\"]",
                r'\\"stoken\\"\s*:\s*\\"([^\\"]+)\\"',
            ]
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    logger.info("stoken found via HTML parsing")
                    return match.group(1)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.error("HTML parsing network error: %s", exc)
            raise QuarkNetworkError(f"Network error during HTML parsing: {exc}") from exc
        except Exception as exc:
            logger.exception("get_stoken failed")
            raise QuarkAPIError(f"Failed to get stoken: {exc}") from exc

        raise QuarkAPIError("stoken not found in share page HTML")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((QuarkNetworkError, httpx.TimeoutException)),
        reraise=True
    )
    async def get_or_create_dir(self, path: str) -> str:
        try:
            normalized = posixpath.normpath(path or "/")
            if normalized in (".", ""):
                normalized = "/"
            segments = [seg for seg in normalized.strip("/").split("/") if seg]
            parent_fid = "0"
            for segment in segments:
                existing = await self._find_child_dir(parent_fid, segment)
                if existing:
                    parent_fid = existing
                    continue
                parent_fid = await self._create_dir(parent_fid, segment)
            logger.info("directory created/resolved: %s -> fid=%s", path, parent_fid)
            return parent_fid
        except QuarkAuthError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.error("get_or_create_dir network error for path=%s: %s", path, exc)
            raise QuarkNetworkError(f"Network error during directory creation: {exc}") from exc
        except Exception as exc:
            logger.exception("get_or_create_dir failed for path=%s: %s", path, exc)
            raise QuarkAPIError(f"Failed to create directory {path}: {exc}") from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((QuarkNetworkError, httpx.TimeoutException)),
        reraise=True
    )
    async def share_save(
        self,
        share_fid_token: str,
        stoken: str,
        to_pdir_fid: str,
        share_url: Optional[str] = None,
        file_fid: Optional[str] = None,
    ) -> bool:
        try:
            if share_url:
                share_code, _ = self._extract_share_info(share_url)
                result = await self._share_page_save(
                    share_code=share_code,
                    stoken=stoken,
                    to_pdir_fid=to_pdir_fid,
                    share_fid_token=share_fid_token,
                    file_fid=file_fid,
                )
                if result is not None:
                    return result

            payload_variants = self._share_save_payload_variants(share_fid_token, stoken, to_pdir_fid)
            extra_hosts = []
            use_safe_host = os.getenv("QUARK_SHARE_SAVE_USE_SAFE_HOST", "1").strip().lower() not in (
                "0",
                "false",
                "no",
            )
            if use_safe_host:
                safe_host = await self._get_share_safe_host_url()
                if safe_host:
                    extra_hosts.append(safe_host)
            for base_url in self._share_save_base_urls(extra_hosts=tuple(extra_hosts) or None):
                url = f"{base_url}/1/clouddrive/share/share_save"
                skip_host = False
                for field_name, payload in payload_variants:
                    try:
                        data = await self._request_json("POST", url, params=self._base_params(), payload=payload)
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code if exc.response else None
                        if status == 404:
                            logger.warning("share_save 404 on base_url=%s, trying next host", base_url)
                            skip_host = True
                            break
                        if status == 403 and exc.response is not None:
                            message = ""
                            try:
                                response_data = exc.response.json()
                                if isinstance(response_data, dict):
                                    message = response_data.get("message") or response_data.get("error") or ""
                            except Exception:
                                message = exc.response.text or ""
                            if "csrf" in str(message).lower():
                                logger.warning("share_save 403 csrf on base_url=%s, trying next host", base_url)
                                skip_host = True
                                break
                        raise

                    if data.get("status") == 200:
                        logger.info("share_save succeeded for fid=%s using field=%s", share_fid_token, field_name)
                        return True

                    error_msg = data.get("message") or data.get("error") or "Unknown error"
                    logger.warning(
                        "share_save failed for fid=%s field=%s status=%s message=%s",
                        share_fid_token,
                        field_name,
                        data.get("status"),
                        error_msg,
                    )

                    if "require login" in str(error_msg).lower() or "guest" in str(error_msg).lower():
                        raise QuarkAuthError(f"Authentication failed: {error_msg}")

                    if not self._should_retry_share_save(error_msg):
                        return False

                if skip_host:
                    continue

            return False
        except QuarkAuthError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.error("share_save network error for fid=%s: %s", share_fid_token, exc)
            raise QuarkNetworkError(f"Network error during share_save: {exc}") from exc
        except Exception as exc:
            logger.exception("share_save unexpected error for fid=%s: %s", share_fid_token, exc)
            raise QuarkAPIError(f"share_save failed: {exc}") from exc

    async def _share_page_save(
        self,
        share_code: str,
        stoken: str,
        to_pdir_fid: str,
        share_fid_token: str,
        file_fid: Optional[str],
    ) -> Optional[bool]:
        if not share_code:
            logger.warning("share_code missing, skip sharepage/save")
            return None
        resolved_fid_token = None
        if not file_fid and share_fid_token:
            file_fid, resolved_fid_token = await self._resolve_share_fid(share_code, stoken, share_fid_token)
        if not file_fid:
            logger.warning("file fid missing, skip sharepage/save")
            return None

        payload = {
            "fid_list": [file_fid],
            "to_pdir_fid": to_pdir_fid,
            "pwd_id": share_code,
            "stoken": stoken,
            "pdir_fid": "0",
            "scene": "link",
        }
        if resolved_fid_token:
            payload["share_fid_token_list"] = [resolved_fid_token]
        elif share_fid_token:
            payload["share_fid_token_list"] = [share_fid_token]

        logger.info("sharepage/save payload: fid=%s, fid_token=%s, share_code=%s, stoken=%s", 
                   file_fid, resolved_fid_token or share_fid_token, share_code, stoken[:10] + "..." if stoken else "None")

        params = {
            **self._base_params(),
            "__dt": "208097",
            "__t": self._now_ms(),
        }

        extra_hosts = []
        use_safe_host = os.getenv("QUARK_SHARE_SAVE_USE_SAFE_HOST", "1").strip().lower() not in (
            "0",
            "false",
            "no",
        )
        if use_safe_host:
            safe_host = await self._get_share_safe_host_url()
            if safe_host:
                extra_hosts.append(safe_host)

        base_urls = list(self._share_save_base_urls())
        for host in extra_hosts:
            if host not in base_urls:
                base_urls.append(host)

        for base_url in base_urls:
            url = f"{base_url}/1/clouddrive/share/sharepage/save"
            try:
                data = await self._request_json("POST", url, params=params, payload=payload)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response else None
                if status == 404:
                    logger.warning("sharepage/save 404 on base_url=%s, trying next host", base_url)
                    continue
                if status == 403 and exc.response is not None:
                    message = ""
                    error_code = ""
                    try:
                        response_data = exc.response.json()
                        if isinstance(response_data, dict):
                            message = response_data.get("message") or response_data.get("error") or ""
                            error_code = response_data.get("code") or ""
                    except Exception:
                        message = exc.response.text or ""
                    logger.error(
                        "sharepage/save 403 error on base_url=%s: code=%s, message=%s, fid=%s, fid_token=%s",
                        base_url, error_code, message, file_fid, resolved_fid_token or share_fid_token[:10] + "..." if (resolved_fid_token or share_fid_token) else "None"
                    )
                    if error_code == 41020:
                        logger.error("Token validation failed (code 41020): fid and fid_token do not match or token expired")
                        logger.warning("sharepage/save token validation failed, falling back to share_save")
                        return None
                    if "csrf" in str(message).lower():
                        logger.warning(
                            "sharepage/save 403 csrf on base_url=%s, trying next host",
                            base_url,
                        )
                        continue
                raise
            if self._is_ok_response(data):
                logger.info("sharepage/save succeeded for fid=%s", file_fid)
                return True

            error_msg = data.get("message") or data.get("error") or "Unknown error"
            error_code = data.get("code") or ""
            logger.warning(
                "sharepage/save failed status=%s code=%s message=%s, fid=%s, fid_token=%s",
                data.get("status"), error_code, error_msg, file_fid, resolved_fid_token or share_fid_token[:10] + "..." if (resolved_fid_token or share_fid_token) else "None"
            )

            if "require login" in str(error_msg).lower() or "guest" in str(error_msg).lower():
                raise QuarkAuthError(f"Authentication failed: {error_msg}")

            if not self._should_retry_share_save(error_msg):
                return False

        return False

    def _normalize_share_url(self, share_url: str, share_code: str, passcode: str) -> str:
        share_url = (share_url or "").strip()
        if share_url.startswith("http://") or share_url.startswith("https://"):
            return share_url
        if share_url.startswith("pan.quark.cn") or share_url.startswith("drive.quark.cn"):
            return f"https://{share_url}"
        if "/" in share_url:
            return f"https://{share_url}"
        url = f"https://pan.quark.cn/s/{share_code}"
        if passcode:
            return f"{url}?pwd={passcode}"
        return url

    def _extract_share_info(self, share_url: str) -> Tuple[str, str]:
        share_url = (share_url or "").strip()
        if not share_url:
            raise ValueError("share_url is empty")

        if "://" not in share_url and "/" not in share_url:
            return share_url, ""

        candidate = share_url
        if share_url.startswith("pan.quark.cn") or share_url.startswith("drive.quark.cn"):
            candidate = f"https://{share_url}"

        match = re.search(r"/s/([A-Za-z0-9_-]+)", candidate)
        if not match:
            raise ValueError(f"Unable to parse share code from: {share_url}")

        parsed = urlparse(candidate)
        query = parse_qs(parsed.query)
        passcode = (
            (query.get("pwd") or query.get("passcode") or query.get("password") or query.get("p") or [""])[0]
        )
        return match.group(1), passcode

    def _share_save_payload_variants(
        self,
        share_fid_token: str,
        stoken: str,
        to_pdir_fid: str,
    ) -> Tuple[Tuple[str, Dict[str, Any]], ...]:
        preferred = os.getenv("QUARK_SHARE_SAVE_FID_FIELD", "fid_list").strip() or "fid_list"
        candidates = (preferred, "fid_list", "share_fid_token_list", "fid_token_list")
        variants = []
        seen = set()
        for field_name in candidates:
            if field_name in seen:
                continue
            seen.add(field_name)
            payload = {
                field_name: [share_fid_token],
                "stoken": stoken,
                "to_pdir_fid": to_pdir_fid,
            }
            variants.append((field_name, payload))
        return tuple(variants)

    async def _resolve_share_fid(
        self,
        share_code: str,
        stoken: str,
        share_fid_token: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        params = {
            **self._base_params(),
            "pwd_id": share_code,
            "stoken": stoken,
            "pdir_fid": "0",
            "force": "0",
            "_page": "1",
            "_size": "200",
            "_fetch_banner": "1",
            "_fetch_share": "1",
            "_fetch_total": "1",
            "_sort": "file_type:asc,updated_at:desc",
            "__dt": "1589",
            "__t": self._now_ms(),
        }
        url = f"{self.share_base_url}/1/clouddrive/share/sharepage/detail"
        try:
            data = await self._request_json("GET", url, params=params)
        except Exception:
            logger.warning("failed to resolve fid via sharepage/detail")
            return None, None

        items = (data.get("data") or {}).get("list") or []
        for item in items:
            if item.get("share_fid_token") != share_fid_token:
                continue
            fid = item.get("fid") or item.get("file_id")
            fid_token = item.get("share_fid_token")
            if fid and fid_token:
                logger.info("resolved fid=%s, fid_token=%s from sharepage/detail", fid, fid_token[:10] + "..." if fid_token else "None")
                return str(fid), fid_token
        logger.warning("share fid not found in sharepage/detail for share_fid_token=%s", share_fid_token[:10] + "..." if share_fid_token else "None")
        return None, None

    async def _get_share_safe_host_url(self) -> Optional[str]:
        if self._share_safe_host_url is not None:
            return self._share_safe_host_url or None
        try:
            config = await self._get_config()
            host = ((config.get("data") or {}).get("share_safe_host") or "").strip()
            if host:
                if not host.startswith("http"):
                    host = f"https://{host}"
                self._share_safe_host_url = host.rstrip("/")
                return self._share_safe_host_url
        except Exception:
            logger.warning("share_safe_host resolution failed")
        self._share_safe_host_url = ""
        return None

    def _share_save_base_urls(self, extra_hosts: Optional[Tuple[str, ...]] = None) -> Tuple[str, ...]:
        preferred = os.getenv("QUARK_SHARE_SAVE_BASE_URL", "").strip()
        list_env = os.getenv("QUARK_SHARE_SAVE_BASE_URLS", "")
        env_candidates = [item.strip() for item in list_env.split(",") if item.strip()]
        candidates = [preferred, *env_candidates]
        if extra_hosts:
            candidates.extend(extra_hosts)
        candidates.extend([self.share_base_url, self.base_url])
        deduped = []
        for candidate in candidates:
            if not candidate:
                continue
            normalized = candidate.rstrip("/")
            if normalized in deduped:
                continue
            deduped.append(normalized)
        return tuple(deduped)

    def _is_ok_response(self, data: Dict[str, Any]) -> bool:
        status = data.get("status")
        code = data.get("code")
        return status == 200 or code == 0

    def _should_retry_share_save(self, error_msg: str) -> bool:
        if not error_msg:
            return False
        text = str(error_msg).lower()
        return any(
            token in text
            for token in (
                "fid_list",
                "share_fid_token_list",
                "fid_token_list",
                "param",
                "missing",
                "required",
            )
        )

    async def _find_child_dir(self, parent_fid: str, name: str) -> Optional[str]:
        page = 1
        size = 200
        while True:
            items, total = await self._list_dir(parent_fid, page, size)
            for item in items:
                if item.get("file_name") != name:
                    continue
                if bool(item.get("dir")) or item.get("file_type") == 0:
                    fid = item.get("fid") or item.get("file_id")
                    if fid:
                        return str(fid)
            if not items:
                break
            if total is not None and page * size >= total:
                break
            if total is None and len(items) < size:
                break
            page += 1
        return None

    async def _list_dir(self, parent_fid: str, page: int, size: int) -> Tuple[list, Optional[int]]:
        params = {
            **self._base_params(),
            "pdir_fid": parent_fid,
            "_page": str(page),
            "_size": str(size),
            "_fetch_total": "1",
            "_fetch_sub_dirs": "0",
            "_sort": "file_type:asc,updated_at:desc",
        }
        url = f"{self.base_url}/1/clouddrive/file/sort"
        data = await self._request_json("GET", url, params=params)
        payload = data.get("data") or {}
        items = payload.get("list") or []
        total = None
        for container in (payload, data.get("metadata") or {}, payload.get("metadata") or {}):
            for key in ("_total", "total", "_count", "count"):
                if key in container and isinstance(container[key], int):
                    total = container[key]
                    break
            if total is not None:
                break
        return items, total

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((QuarkNetworkError, httpx.TimeoutException)),
        reraise=True
    )
    async def _create_dir(self, parent_fid: str, name: str) -> str:
        payload = {
            "pdir_fid": parent_fid,
            "file_name": name,
            "dir_path": "",
            "dir_init_lock": False,
        }
        try:
            url = f"{self.base_url}/1/clouddrive/file"
            data = await self._request_json("POST", url, params=self._base_params(), payload=payload)
            if data.get("status") != 200:
                message = data.get("message") or data.get("error") or "create folder failed"
                if "require login" in str(message).lower() or "guest" in str(message).lower():
                    raise QuarkAuthError(f"Authentication failed: {message}")
                raise QuarkAPIError(f"Create directory failed: {message}")
            folder = data.get("data") or {}
            fid = folder.get("fid") or folder.get("file_id")
            if not fid:
                raise QuarkAPIError("create folder returned no fid")
            logger.info("directory created: name=%s, fid=%s", name, fid)
            return str(fid)
        except QuarkAuthError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.error("_create_dir network error: %s", exc)
            raise QuarkNetworkError(f"Network error during directory creation: {exc}") from exc
        except Exception as exc:
            logger.exception("_create_dir failed: %s", exc)
            raise QuarkAPIError(f"Failed to create directory: {exc}") from exc

    async def _request_json(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        merged_headers = dict(self.client.headers)
        if headers:
            merged_headers.update(headers)
        self._log_request(method, url, merged_headers, params, payload)

        try:
            response = await self.client.request(
                method,
                url,
                params=params,
                json=payload,
                headers=merged_headers,
            )
            status_code = response.status_code
            try:
                data = response.json()
            except Exception:
                data = response.text
            logger.info("response status: %s", status_code)
            logger.info("response body: %s", data)
            response.raise_for_status()
            if not isinstance(data, dict):
                raise RuntimeError("expected JSON response body, got non-JSON")
            return data
        except Exception:
            logger.exception("request failed: %s %s", method, url)
            raise

    async def _get_share_token(self, share_code: str, passcode: str) -> str:
        params = {
            **self._base_params(),
            "__dt": "994",
            "__t": self._now_ms(),
        }
        payload = {"pwd_id": share_code, "passcode": passcode}
        url = f"{self.share_base_url}/1/clouddrive/share/sharepage/token"
        data = await self._request_json("POST", url, params=params, payload=payload)
        if data.get("status") != 200 or not data.get("data"):
            message = data.get("message") or data.get("error") or "share token failed"
            raise RuntimeError(message)
        stoken = data["data"].get("stoken")
        if not stoken:
            raise RuntimeError("missing stoken in share token response")
        return stoken

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _base_params(self) -> Dict[str, str]:
        return {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}

    def _log_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]],
        payload: Optional[Dict[str, Any]],
    ) -> None:
        logger.info("request method: %s", method)
        logger.info("request url: %s", url)
        logger.info("request headers: %s", headers)
        logger.info("request params: %s", params)
        logger.info("request payload: %s", payload)
