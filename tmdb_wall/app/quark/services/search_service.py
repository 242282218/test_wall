import asyncio
import time
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.quark.logger import logger
from app.quark.utils.exceptions import QuarkAPIException, DatabaseException
from app.quark.core.confidence import ConfidenceCalculator
from app.quark.core.media_fetcher import MediaFetcher
from app.quark.core.scoring import compute_overall, mark_best, rank_results
from app.quark.core.models import MatchResult, MediaInfo
from app.quark.core.quality import QualityEvaluator
from app.quark.core.quark_client import AsyncQuarkAPIClient
from app.quark.schemas.search import ResourceDto, MediaDto, SearchResponse
from app.quark.models.media import Media
from app.quark.models.resource import Resource
from app.quark.utils.name_normalizer import normalize_filename

settings = get_settings()


class SearchService:
    def __init__(self):
        self.media_fetcher = MediaFetcher()
        self.quark_client = AsyncQuarkAPIClient()
        self.confidence = ConfidenceCalculator()
        self.quality = QualityEvaluator()

    async def _run_blocking(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)

    async def search_by_tmdb_id(self, tmdb_id: int, max_results: int, db: Session, media_type: str = "movie") -> SearchResponse:
        logger.info(f"通过 TMDB ID 搜索: {tmdb_id}, 类型: {media_type}")
        # 先尝试指定的 media_type，如果失败则尝试另一个类型
        media_info = await self._run_blocking(self.media_fetcher.fetch_by_tmdb_id, tmdb_id, media_type)
        if not media_info:
            # 如果失败，尝试切换类型（movie <-> tv）
            other_type = "tv" if media_type == "movie" else "movie"
            logger.info(f"尝试切换媒体类型: {other_type}")
            media_info = await self._run_blocking(self.media_fetcher.fetch_by_tmdb_id, tmdb_id, other_type)

        if not media_info:
            logger.warning(f"TMDB ID {tmdb_id} 未找到媒体信息")
            return SearchResponse(success=False, message="媒体不存在", resources=[], total=0)

        return await self._search_common(media_info, media_info.title, max_results, db)

    async def search_by_title(self, title: str, year: Optional[int], max_results: int, db: Session) -> SearchResponse:
        logger.info(f"通过标题搜索: {title}, 年份: {year}")
        media_info = await self._run_blocking(self.media_fetcher.search_by_title, title, year)

        # 即使 TMDB 搜索失败，也尝试直接搜索夸克资源
        if not media_info:
            logger.warning(f"标题 '{title}' 未找到 TMDB 媒体信息，尝试直接搜索夸克资源")
            # 创建一个临时的 MediaInfo 对象用于搜索
            # 或者直接搜索夸克资源，不进行置信度过滤
            return await self._search_direct(title, max_results, db)

        return await self._search_common(media_info, title, max_results, db)
    
    async def _search_direct(self, keyword: str, max_results: int, db: Session) -> SearchResponse:
        """
        直接搜索夸克资源（不进行 TMDB 匹配和置信度过滤）
        用于 TMDB 搜索失败的情况
        """
        start = time.time()
        try:
            logger.info(f"直接搜索夸克资源（无 TMDB 匹配）: {keyword}")
            resources = await self.quark_client.search_resources(keyword, page_size=max_results or settings.quark_search_max_results)
            
            if not resources:
                logger.info(f"未找到夸克资源: {keyword}")
                return SearchResponse(
                    success=True, 
                    media=None,
                    resources=[], 
                    total=0, 
                    query_time=round(time.time()-start, 3),
                    message="未找到相关资源"
                )
            
            # 直接返回所有资源，不进行置信度过滤
            # 保留质量评分最高的4个
            # 同时验证链接有效性，无效链接直接过滤
            from app.quark.utils.link_validator import validate_quark_link
            
            results: List[ResourceDto] = []
            invalid_count = 0
            for r in resources:
                # 验证链接有效性
                is_valid_link = await validate_quark_link(r.link, timeout=3)
                if not is_valid_link:
                    invalid_count += 1
                    logger.debug(f"链接无效，置信度设为0: {r.name[:50]}... ({r.link[:50]}...)")
                    continue

                qinfo = self.quality.evaluate(r.name, r.size)
                quality_score = qinfo.get_score()
                confidence = 0.5
                overall = quality_score
                
                results.append(
                    ResourceDto(
                        name=r.name,
                        link=r.link,
                        confidence=confidence,
                        quality_score=quality_score,
                        overall_score=overall,
                        quality_level=qinfo.level,
                        resolution=qinfo.resolution,
                        codec=qinfo.codec,
                        quality_tags=qinfo.get_tags(),
                        is_best=False,
                    )
                )
            
            if not results:
                logger.info(f"直接搜索未找到可用资源，过滤无效 {invalid_count} 个")
                return SearchResponse(
                    success=True,
                    media=None,
                    resources=[],
                    total=0,
                    query_time=round(time.time()-start, 3),
                    message="未找到可用资源"
                )

            # 按综合评分排序，保留最高的4个
            results = sorted(results, key=lambda x: x.overall_score, reverse=True)
            results = results[:4] if len(results) > 4 else results
            
            # 标记最佳资源
            if results:
                results[0].is_best = True
                logger.info(f"直接搜索找到 {len(resources)} 个资源，过滤无效 {invalid_count} 个，保留质量最高的 {len(results)} 个")
            
            return SearchResponse(
                success=True,
                media=None,
                resources=results,
                total=len(results),
                query_time=round(time.time()-start, 3)
            )
        except Exception as e:
            logger.error(f"直接搜索夸克资源失败: {e}", exc_info=True)
            raise QuarkAPIException(f"搜索失败: {str(e)}")

    async def _search_common(self, media_info: MediaInfo, keyword: str, max_results: int, db: Session) -> SearchResponse:
        start = time.time()
        try:
            logger.info(f"搜索夸克资源: {keyword}")
            resources = await self.quark_client.search_resources(keyword, page_size=max_results or settings.quark_search_max_results)
            if not resources:
                logger.info(f"未找到夸克资源: {keyword}")
                return SearchResponse(
                    success=True,
                    media=self._to_media_dto(media_info),
                    resources=[],
                    total=0,
                    query_time=round(time.time()-start, 3),
                )
        except Exception as e:
            logger.error(f"夸克搜索失败: {e}", exc_info=True)
            raise QuarkAPIException(f"夸克搜索失败: {str(e)}")

        results: List[MatchResult] = []
        invalid_count = 0
        # 不再使用置信度阈值过滤，而是计算所有资源的置信度和评分
        # 同时验证链接有效性，无效链接直接过滤
        from app.quark.utils.link_validator import validate_quark_link
        
        for r in resources:
            # 验证链接有效性
            is_valid_link = await validate_quark_link(r.link, timeout=3)
            if not is_valid_link:
                invalid_count += 1
                logger.debug(f"链接无效，置信度设为0: {r.name[:50]}... ({r.link[:50]}...)")
                continue

            normalized = normalize_filename(r.name)
            md = self.confidence.calculate(normalized.cleaned_title or r.name, media_info)
            confidence = md.get_confidence(self.confidence.weights)
            
            qinfo = self.quality.evaluate(r.name, r.size)
            quality_score = qinfo.get_score()
            overall = compute_overall(confidence, quality_score, settings.quark_search_confidence_weight, settings.quark_search_quality_weight)
            results.append(
                MatchResult(
                    resource=r,
                    media_info=media_info,
                    confidence=confidence,
                    quality_score=quality_score,
                    overall_score=overall,
                    match_details=md,
                    quality_info=qinfo,
                )
            )

        if not results:
            logger.info(f"未找到可用资源，过滤无效 {invalid_count} 个")
            return SearchResponse(
                success=True,
                media=self._to_media_dto(media_info),
                resources=[],
                total=0,
                query_time=round(time.time()-start, 3),
                message="未找到可用资源",
            )
        
        # 相似结果时优先画质，其次综合评分
        results = rank_results(results, settings.quark_search_similarity_band)
        final = results[:4]  # 保留评分最高的4个结果
        
        if len(results) > 4:
            logger.info(f"找到 {len(results)} 个资源，过滤无效 {invalid_count} 个，保留评分最高的 4 个")
        
        # 标记最佳结果
        
        mark_best(final)

        # 落库
        try:
            self._upsert_media(db, media_info)
            self._upsert_resources(db, media_info, final)
        except Exception as e:
            logger.error(f"数据落库失败: {e}", exc_info=True)
            raise DatabaseException(f"数据保存失败: {str(e)}")

        query_time = round(time.time() - start, 3)
        return SearchResponse(
            success=True,
            media=self._to_media_dto(media_info),
            resources=[self._to_resource_dto(r) for r in final],
            total=len(final),
            query_time=query_time,
        )

    def _upsert_media(self, db: Session, media_info: MediaInfo):
        media = db.query(Media).filter(Media.tmdb_id == media_info.tmdb_id).first()
        if not media:
            media = Media(tmdb_id=media_info.tmdb_id, title=media_info.title, year=media_info.year)
            db.add(media)
        else:
            media.title = media_info.title
            media.year = media_info.year
        db.commit()

    def _upsert_resources(self, db: Session, media_info: MediaInfo, results: List[MatchResult]):
        media = db.query(Media).filter(Media.tmdb_id == media_info.tmdb_id).first()
        if not media:
            return
        for res in results:
            existing = db.query(Resource).filter(Resource.link == res.resource.link).first()
            normalized = normalize_filename(res.resource.name)
            
            if not existing:
                existing = Resource(media_id=media.id, link=res.resource.link, name=res.resource.name)
                db.add(existing)
            
            # 更新基础信息
            existing.name = res.resource.name
            existing.confidence = res.confidence
            existing.quality_score = res.quality_score
            existing.overall_score = res.overall_score
            existing.is_best = res.is_best
            
            # 更新画质信息
            existing.quality_level = res.quality_info.level
            existing.resolution = res.quality_info.resolution
            existing.codec = res.quality_info.codec
            existing.size_raw = res.resource.size
            if res.quality_info.total_size_gb:
                existing.total_size_gb = res.quality_info.total_size_gb
            
            # 更新规范化信息
            existing.normalized_name = normalized.normalized_filename
            existing.episode_info = normalized.episode_info
            existing.media_type_detected = normalized.media_type
            
        db.commit()

    def _to_media_dto(self, media: MediaInfo) -> MediaDto:
        return MediaDto(
            tmdb_id=media.tmdb_id,
            title=media.title,
            original_title=media.original_title,
            year=int(media.year) if media.year else None,
            rating=media.rating,
            overview=media.overview,
            poster_path=media.poster_path,
            backdrop_path=media.backdrop_path,
            media_type=media.media_type,
        )

    def _to_resource_dto(self, res: MatchResult) -> ResourceDto:
        # 获取规范化名称
        normalized = normalize_filename(res.resource.name)
        
        return ResourceDto(
            name=res.resource.name,
            normalized_name=normalized.normalized_filename,
            link=res.resource.link,
            confidence=round(res.confidence, 3),
            quality_score=round(res.quality_score, 3),
            overall_score=round(res.overall_score, 3),
            quality_level=res.quality_info.level,
            resolution=res.quality_info.resolution,
            codec=res.quality_info.codec,
            quality_tags=res.quality_info.get_tags(),
            is_best=res.is_best,
        )
