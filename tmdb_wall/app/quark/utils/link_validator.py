# -*- coding: utf-8 -*-
"""
链接验证工具 - 验证夸克网盘链接是否有效
"""
import asyncio
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

import aiohttp

from app.quark.logger import logger


class LinkValidator:
    """夸克网盘链接验证器"""
    
    # 无效链接的特征模式
    INVALID_PATTERNS = [
        r'pan\.quark\.cn/s/[a-f0-9]+#/list/share',  # 分享链接（可能无效）
        r'pan\.quark\.cn/s/[a-f0-9]+/list',  # 列表链接（可能无效）
    ]
    API_URL = "https://drive-h.quark.cn/1/clouddrive/share/sharepage/token"
    INVALID_CODES = {
        41004,  # SHARE_FILE_NOTFOUND
        41005,  # SHARE_FILE_ILLEGAL
        41006,  # SHARE_NOT_EXISTS
        41009,  # DELETED
        41010,  # ILLEGAL
        41011,  # INVALID
        41012,  # CANCELED
        41019,  # EXPIRED
        41024,  # SHARE_NAME_NOT_SUPPORT
        41025,  # SHARE_FILE_LEVEL_LIMITED
        41029,  # USER_SHARE_ILLEGAL
        41030,  # USER_SAVE_ILLEGAL
        41031,  # USER_ACCESS_ILLEGAL
    }
    PASSCODE_CODES = {
        41007,  # PASSCODE_ERROR
        41008,  # NEED_PASSCODE
        41021,  # PASSCODE_TIMES_LIMIT
    }

    @staticmethod
    def _extract_share_id(link: str) -> Optional[str]:
        match = re.search(r'pan\.quark\.cn/s/([A-Za-z0-9]+)', link)
        return match.group(1) if match else None

    @staticmethod
    def _extract_passcode(link: str) -> str:
        try:
            parsed = urlparse(link)
            query = parse_qs(parsed.query)
            for key in ("pwd", "passcode"):
                if key in query and query[key]:
                    return query[key][0]
        except Exception:
            return ""
        return ""

    @staticmethod
    async def _validate_via_api(
        session: aiohttp.ClientSession,
        share_id: str,
        passcode: str,
    ) -> Optional[bool]:
        payload = {
            "pwd_id": share_id,
            "passcode": passcode or "",
            "support_visit_limit_private_share": True,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://pan.quark.cn",
            "Referer": f"https://pan.quark.cn/s/{share_id}",
        }
        try:
            async with session.post(LinkValidator.API_URL, json=payload, headers=headers) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    text = await resp.text()
                    logger.debug(f"API响应非JSON，回退HTML检查: {share_id}..., 内容: {text[:120]}")
                    return None

            code = data.get("code")
            try:
                code = int(code)
            except (TypeError, ValueError):
                logger.debug(f"API响应缺少code字段，回退HTML检查: {share_id}...")
                return None

            if code == 0:
                return True
            if code in LinkValidator.PASSCODE_CODES:
                return True
            if code in LinkValidator.INVALID_CODES:
                logger.debug(f"API判定链接无效: {share_id}..., code={code}")
                return False

            logger.debug(f"API返回未知code，保守认为有效: {share_id}..., code={code}")
            return True
        except Exception as e:
            logger.debug(f"API验证失败，回退HTML检查: {share_id}..., 错误: {e}")
            return None
    
    @staticmethod
    def is_valid_format(link: str) -> bool:
        """
        检查链接格式是否有效
        
        Args:
            link: 夸克网盘链接
            
        Returns:
            如果格式有效返回 True，否则返回 False
        """
        if not link:
            return False
        
        # 基本格式检查
        if not link.startswith(('http://', 'https://')):
            return False
        
        if 'pan.quark.cn' not in link:
            return False
        
        return LinkValidator._extract_share_id(link) is not None
    
    @staticmethod
    async def validate_link(link: str, timeout: int = 5) -> bool:
        """
        验证链接是否可访问（异步）- 改进版
        
        使用基于状态码和页面内容的组合验证算法
        
        Args:
            link: 夸克网盘链接
            timeout: 超时时间（秒）
            
        Returns:
            如果链接可访问返回 True，否则返回 False
        """
        if not LinkValidator.is_valid_format(link):
            return False
        
        # 清理链接（去掉#后面的内容，因为可能是前端路由）
        clean_link = link.split('#')[0] if '#' in link else link
        share_id = LinkValidator._extract_share_id(clean_link)
        if not share_id:
            return False
        passcode = LinkValidator._extract_passcode(clean_link)

        async def _validate() -> bool:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                api_result = await LinkValidator._validate_via_api(session, share_id, passcode)
                if api_result is not None:
                    return api_result

                # 设置合适的请求头
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }

                # 使用GET请求获取页面内容（因为需要检查内容）
                async with session.get(clean_link, headers=headers, allow_redirects=True, max_redirects=5) as resp:
                    status = resp.status

                    # 明确无效的状态码
                    if status == 404:
                        logger.debug(f"链接无效（404）: {link[:50]}...")
                        return False

                    if status == 403:
                        logger.debug(f"链接无权限（403）: {link[:50]}...")
                        return False

                    if status >= 500:
                        logger.debug(f"服务器错误（{status}）: {link[:50]}...")
                        return False

                    # 对于200状态码，检查页面内容
                    if status == 200:
                        try:
                            content = await resp.text()
                            content = content[:8192] if len(content) > 8192 else content

                            # 检查是否包含明确的错误信息（在标题中）
                            import re
                            error_patterns = [
                                r'<title>[^<]*(?:链接不存在|分享不存在|文件不存在|链接已失效|分享已取消)[^<]*</title>',
                                r'<h1[^>]*>[^<]*(?:链接不存在|分享不存在)[^<]*</h1>',
                            ]

                            has_error_in_title = False
                            for pattern in error_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    has_error_in_title = True
                                    break

                            if has_error_in_title:
                                logger.debug(f"链接无效（页面包含错误信息）: {link[:50]}...")
                                return False

                            # 检查是否包含有效指示
                            valid_indicators = [
                                'pan.quark.cn' in content,
                                'quark.cn' in content,
                                '文件列表' in content,
                                '分享链接' in content,
                            ]

                            # 对于普通链接，使用原有逻辑
                            if any(valid_indicators) or len(content) > 500:
                                return True

                            # 内容太少，可能无效
                            if len(content) < 100:
                                logger.debug(f"链接可能无效（内容太少）: {link[:50]}...")
                                return False

                            # 其他情况，保守地认为有效
                            return True

                        except Exception as e:
                            logger.debug(f"读取页面内容失败: {link[:50]}..., 错误: {e}")
                            # 读取失败，保守地认为可能有效
                            return True

                    # 3xx重定向状态码，认为可能有效
                    if 300 <= status < 400:
                        return True

                    # 其他状态码，保守地认为可能有效
                    return True

        try:
            return await asyncio.wait_for(_validate(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.debug(f"链接验证超时: {link[:50]}...")
            return False
        except aiohttp.ClientError as e:
            logger.debug(f"链接验证失败: {link[:50]}..., 错误: {e}")
            return False
        except Exception as e:
            logger.warning(f"链接验证异常: {link[:50]}..., 错误: {e}")
            # 发生异常时，保守地认为链接可能有效（避免误判）
            return True


async def validate_quark_link(link: str, timeout: int = 5) -> bool:
    """
    验证夸克网盘链接是否有效（便捷函数）
    
    Args:
        link: 夸克网盘链接
        timeout: 超时时间（秒）
        
    Returns:
        如果链接有效返回 True，否则返回 False
    """
    return await LinkValidator.validate_link(link, timeout)

