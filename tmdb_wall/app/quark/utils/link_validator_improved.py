# -*- coding: utf-8 -*-
"""
改进的链接验证工具 - 更准确地验证夸克网盘链接是否有效
"""
import asyncio
import re
from typing import Optional, List, Dict

import aiohttp

from app.quark.logger import logger


class ImprovedLinkValidator:
    """改进的夸克网盘链接验证器"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, bool] = {}  # 简单的内存缓存
    
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=10)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def is_valid_format(self, link: str) -> bool:
        """检查链接格式是否有效"""
        if not link:
            return False
        
        if not link.startswith(('http://', 'https://')):
            return False
        
        if 'pan.quark.cn' not in link:
            return False
        
        # 匹配夸克网盘链接格式
        # 格式1: https://pan.quark.cn/s/xxxxx#/list/share
        # 格式2: https://pan.quark.cn/s/xxxxx?pwd=xxxxx
        # 格式3: https://pan.quark.cn/s/xxxxx?entry=bihu
        pattern = r'pan\.quark\.cn/s/[a-f0-9]{10,}'
        return bool(re.search(pattern, link))
    
    async def validate_link(self, link: str, timeout: int = 8) -> Dict[str, any]:
        """
        验证链接是否有效，返回详细信息
        
        Returns:
            {
                'valid': bool,           # 是否有效
                'accessible': bool,      # 是否可访问
                'status_code': int,      # HTTP状态码
                'has_content': bool,     # 是否有内容
                'error': str,           # 错误信息
                'link_type': str,       # 链接类型
            }
        """
        result = {
            'valid': False,
            'accessible': False,
            'status_code': None,
            'has_content': False,
            'error': None,
            'link_type': 'unknown',
        }
        
        # 格式检查
        if not self.is_valid_format(link):
            result['error'] = '格式无效'
            return result
        
        # 检查缓存
        if link in self.cache:
            result['valid'] = self.cache[link]
            result['accessible'] = self.cache[link]
            return result
        
        # 判断链接类型
        if '#/list/share' in link:
            result['link_type'] = 'share_list'
        elif '?pwd=' in link or '?entry=' in link:
            result['link_type'] = 'with_password'
        else:
            result['link_type'] = 'simple'
        
        try:
            # 使用GET请求获取实际内容，因为HEAD可能不准确
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            
            async with self.session.get(link, headers=headers, allow_redirects=True, max_redirects=5) as resp:
                result['status_code'] = resp.status
                
                # 状态码检查
                if resp.status == 404:
                    result['error'] = '链接不存在（404）'
                    self.cache[link] = False
                    return result
                
                if resp.status == 403:
                    result['error'] = '无权限访问（403）'
                    self.cache[link] = False
                    return result
                
                if resp.status >= 500:
                    result['error'] = f'服务器错误（{resp.status}）'
                    self.cache[link] = False
                    return result
                
                # 读取部分内容进行检查（使用text()方法，会自动处理编码）
                try:
                    # 先读取部分内容（限制大小以避免下载整个页面）
                    content_text = await resp.text()
                    # 如果内容太长，只取前8192个字符
                    if len(content_text) > 8192:
                        content_text = content_text[:8192]
                    result['has_content'] = len(content_text) > 100
                except Exception as e:
                    logger.debug(f"读取响应内容失败: {e}")
                    content_text = ""
                    result['has_content'] = False
                
                    # 检查内容中是否包含有效的指示
                    if resp.status == 200 or (200 <= resp.status < 400):
                        # 检查是否包含明确的错误页面关键词（需要更精确）
                        error_keywords = [
                            '分享不存在',
                            '链接不存在',
                            '文件不存在',
                            '链接已失效',
                            '分享已取消',
                            '链接已过期',
                        ]
                        
                        # 检查是否包含错误提示（在标题或主要位置）
                        content_lower = content_text.lower()
                        has_error = False
                        for keyword in error_keywords:
                            # 检查是否在标题标签或明显位置出现
                            if keyword in content_text:
                                # 进一步检查，确保不是误判
                                if f'<title>{keyword}' in content_text or f'<h1>{keyword}' in content_text or f'<title>{keyword}' in content_text:
                                    has_error = True
                                    break
                                # 检查是否是主要内容
                                error_pos = content_text.find(keyword)
                                if error_pos > 0 and error_pos < 2000:  # 在前2KB内
                                    has_error = True
                                    break
                        
                        # 检查是否包含有效页面关键词
                        valid_keywords = [
                            'quark.cn',
                            'pan.quark.cn',
                            '文件列表',
                            '分享链接',
                            '提取码',
                            'file-list',
                            '文件分享',
                            '网盘',
                        ]
                        
                        has_valid = any(keyword in content_text for keyword in valid_keywords)
                        
                        # 检查页面标题
                        title_match = False
                        if '<title>' in content_text:
                            title_start = content_text.find('<title>')
                            title_end = content_text.find('</title>', title_start)
                            if title_start >= 0 and title_end > title_start:
                                title_text = content_text[title_start:title_end+8].lower()
                                if 'quark' in title_text or '夸克' in title_text:
                                    title_match = True
                        
                        # 判断逻辑（更保守的策略）
                        if has_error and not has_valid and not title_match:
                            # 明确包含错误信息，且没有有效指示
                            result['valid'] = False
                            result['accessible'] = False
                            result['error'] = '页面包含错误信息'
                            self.cache[link] = False
                        elif has_valid or title_match or len(content_text) > 1000:
                            # 有有效关键词、标题匹配或内容足够长，认为可能有效
                            result['valid'] = True
                            result['accessible'] = True
                            self.cache[link] = True
                        elif len(content_text) > 100:
                            # 内容较少但有一定长度，保守地认为可能有效（避免误判）
                            result['valid'] = True
                            result['accessible'] = True
                            result['error'] = '内容较少，无法确定'
                            self.cache[link] = True
                        else:
                            # 内容太少，可能无效
                            result['valid'] = False
                            result['accessible'] = False
                            result['error'] = '页面内容太少'
                            self.cache[link] = False
                else:
                    result['error'] = f'状态码异常（{resp.status}）'
                    result['valid'] = False
                    self.cache[link] = False
                    
        except asyncio.TimeoutError:
            result['error'] = '请求超时'
            result['valid'] = False
            self.cache[link] = False
        except aiohttp.ClientError as e:
            result['error'] = f'客户端错误: {str(e)}'
            result['valid'] = False
            self.cache[link] = False
        except Exception as e:
            logger.warning(f"链接验证异常: {link[:50]}..., 错误: {e}")
            result['error'] = f'验证异常: {str(e)}'
            # 发生异常时，保守地认为可能有效（避免误判有效链接）
            result['valid'] = True
            self.cache[link] = True
        
        return result
    
    async def batch_validate(self, links: List[str], timeout: int = 8, concurrency: int = 5) -> Dict[str, Dict]:
        """
        批量验证链接
        
        Args:
            links: 链接列表
            timeout: 每个链接的超时时间
            concurrency: 并发数
            
        Returns:
            {link: validation_result, ...}
        """
        semaphore = asyncio.Semaphore(concurrency)
        results = {}
        
        async def validate_one(link: str):
            async with semaphore:
                result = await self.validate_link(link, timeout)
                return link, result
        
        tasks = [validate_one(link) for link in links]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        for item in completed:
            if isinstance(item, Exception):
                logger.error(f"批量验证异常: {item}")
                continue
            link, result = item
            results[link] = result
        
        return results


# 便捷函数
async def validate_quark_link_improved(link: str, timeout: int = 8) -> bool:
    """改进的链接验证（便捷函数）"""
    async with ImprovedLinkValidator() as validator:
        result = await validator.validate_link(link, timeout)
        return result.get('valid', False)


async def batch_validate_links(links: List[str], timeout: int = 8, concurrency: int = 5) -> Dict[str, Dict]:
    """批量验证链接（便捷函数）"""
    async with ImprovedLinkValidator() as validator:
        return await validator.batch_validate(links, timeout, concurrency)

