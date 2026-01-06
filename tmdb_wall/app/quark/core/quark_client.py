import asyncio
import re
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set

import aiohttp

from app.config import get_settings
from app.quark.logger import logger

settings = get_settings()


@dataclass
class QuarkResource:
    id: int
    name: str
    link: str
    size: str
    updatetime: str
    categoryid: int
    uploaderid: str
    views: int

    def to_dict(self) -> Dict:
        return asdict(self)


class AsyncQuarkAPIClient:
    """
    精简版趣盘搜夸克资源客户端（爬虫源）。
    """

    def __init__(
        self,
        base_url: str | None = None,
        max_retries: int | None = None,
        retry_delay: float = 1.0,
        rate_limit: float | None = None,
        timeout: int | None = None,
    ):
        base_url = base_url or settings.quark_search_base_url
        max_retries = max_retries or settings.quark_search_max_retries
        rate_limit = rate_limit if rate_limit is not None else settings.quark_search_rate_limit
        timeout = timeout or settings.quark_search_timeout
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.last_request_time = 0.0
        self.seen_ids: Set[int] = set()

        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
        }

    async def _rate_limit_wait(self):
        now = time.time()
        delta = now - self.last_request_time
        if delta < self.rate_limit:
            await asyncio.sleep(self.rate_limit - delta)
        self.last_request_time = time.time()

    async def _post(self, url: str, data: Optional[Dict] = None) -> Optional[Dict]:
        await self._rate_limit_wait()
        for attempt in range(self.max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=self.headers, json=data) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        elif resp.status != 200:
                            # 记录非 200 状态码的错误信息
                            try:
                                error_data = await resp.json()
                                logger.warning(f"夸克搜索 API HTTP {resp.status}: {error_data}")
                            except:
                                text = await resp.text()
                                logger.warning(f"夸克搜索 API HTTP {resp.status}: {text[:200]}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay * (attempt + 1))
            except Exception as e:
                logger.warning(f"夸克搜索请求异常 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
        return None

    def _parse_resource(self, raw: Dict) -> Optional[QuarkResource]:
        try:
            link = raw.get("url") or raw.get("link") or ""
            if not link or "pan.quark.cn" not in link:
                return None
            
            # 清理资源名称中的 HTML 标签（如 <em> 标签）
            name = raw.get("title") or raw.get("filename") or "未知资源"
            name = re.sub(r'<[^>]+>', '', name)  # 移除所有 HTML 标签
            name = re.sub(r'\s+', ' ', name).strip()  # 清理多余空格
            
            # 确保所有必需字段都有值
            resource_id = raw.get("id", 0) or 0
            uploaderid = raw.get("uploaderid", "") or ""
            if not isinstance(uploaderid, str):
                uploaderid = str(uploaderid) if uploaderid is not None else ""
            
            return QuarkResource(
                id=resource_id,
                name=name,
                link=link,
                size=raw.get("size", "") or "",
                updatetime=raw.get("updatetime", "") or "",
                categoryid=raw.get("categoryid", 0) or 0,
                uploaderid=uploaderid,
                views=raw.get("views", 0) or 0,
            )
        except Exception as e:
            # 记录解析失败的详细信息，便于调试
            logger.warning(f"资源解析失败: {e}, raw_id={raw.get('id')}, link={link[:50] if 'link' in locals() else 'N/A'}")
            return None

    async def search_resources(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 100,
        deduplicate: bool = True,
    ) -> List[QuarkResource]:
        url = f"{self.base_url}/search"
        # 修复 API 参数格式（参考原始项目）
        payload = {
            "keyword": keyword,  # 修复：使用 keyword 而不是 searchKey
            "categoryid": 0,  # 分类ID（0表示全部）
            "filetypeid": 0,  # 文件类型ID（0表示全部）
            "courseid": 1,  # 课程ID
            "page": page,
            "pageSize": page_size,
            "sortBy": "sort",  # 修复：使用 sortBy 而不是 sort
            "order": "desc",
            "offset": (page - 1) * page_size,  # 添加 offset 字段
        }
        resp = await self._post(url, payload)
        if not resp:
            logger.warning(f"夸克搜索 API 调用失败: 未收到响应 (关键词: {keyword})")
            return []
        if resp.get("code") != 200:
            # 记录错误信息以便调试
            logger.warning(f"夸克搜索 API 错误: code={resp.get('code')}, message={resp.get('message', '未知错误')}, 关键词: {keyword}")
            return []
        data = resp.get("data", {})
        raw_list = data.get("list", []) if isinstance(data, dict) else data
        if not raw_list:
            logger.info(f"夸克搜索 API 返回空列表 (关键词: {keyword})")
            return []
        
        logger.info(f"夸克搜索找到 {len(raw_list)} 个原始资源 (关键词: {keyword})")
        resources: List[QuarkResource] = []
        parsed_count = 0
        for r in raw_list:
            parsed = self._parse_resource(r)
            if parsed:
                resources.append(parsed)
                parsed_count += 1
        
        if parsed_count == 0 and len(raw_list) > 0:
            logger.warning(f"所有 {len(raw_list)} 个资源解析失败 (关键词: {keyword})")
        elif parsed_count < len(raw_list):
            logger.info(f"解析成功: {parsed_count}/{len(raw_list)} (关键词: {keyword})")
        if deduplicate:
            unique: Dict[int, QuarkResource] = {}
            for r in resources:
                if r.id not in unique:
                    unique[r.id] = r
            resources = list(unique.values())
        return resources

