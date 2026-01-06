import asyncio

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.quark.deps import get_db
from app.quark.models.media import Media
from app.quark.models.resource import Resource
from app.quark.core.quality import QualityEvaluator
from app.quark.utils.link_validator import validate_quark_link

router = APIRouter(tags=["media"])
quality = QualityEvaluator()


def _resource_payload(resource: Resource) -> dict:
    qinfo = quality.evaluate(resource.name, resource.size_raw)
    resolution = resource.resolution or qinfo.resolution
    codec = resource.codec or qinfo.codec
    quality_level = resource.quality_level or qinfo.level
    tags = qinfo.get_tags()
    if not tags and resolution:
        tags = [resolution]
    return {
        "name": resource.name,
        "link": resource.link,
        "confidence": resource.confidence,
        "quality_score": resource.quality_score,
        "overall_score": resource.overall_score,
        "quality_level": quality_level,
        "resolution": resolution,
        "codec": codec,
        "quality_tags": tags,
        "total_size_gb": resource.total_size_gb,
        "size_raw": resource.size_raw,
        "is_best": resource.is_best,
    }


async def _filter_valid_resources(items: list[Resource]) -> tuple[list[Resource], int]:
    if not items:
        return [], 0
    tasks = [validate_quark_link(r.link, timeout=3) for r in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid: list[Resource] = []
    invalid_count = 0
    for resource, ok in zip(items, results):
        if isinstance(ok, Exception) or not ok:
            invalid_count += 1
            continue
        valid.append(resource)
    return valid, invalid_count


@router.get("/media/{media_id}/resources")
async def list_resources(
    media_id: int,
    sort: str = Query("score", pattern="^(score|size|views)$"),
    quality: str | None = Query(None, pattern="^(4k|1080p|720p)$"),
    db: Session = Depends(get_db),
):
    q = db.query(Resource).filter(Resource.media_id == media_id)
    if quality:
        q = q.filter(Resource.resolution.ilike(f"%{quality.upper()}%"))
    if sort == "score":
        q = q.order_by(Resource.overall_score.desc())
    elif sort == "size":
        q = q.order_by(Resource.total_size_gb.desc())
    elif sort == "views":
        q = q.order_by(Resource.views.desc())
    items = q.all()
    items, invalid_count = await _filter_valid_resources(items)
    message = "未找到可用资源" if not items else ""
    return {
        "success": True,
        "media": db.query(Media).filter(Media.id == media_id).first(),
        "data": [_resource_payload(r) for r in items],
        "total": len(items),
        "message": message,
        "invalid_count": invalid_count,
    }


@router.get("/media/by-tmdb/{tmdb_id}/resources")
async def list_resources_by_tmdb_id(
    tmdb_id: int,
    sort: str = Query("score", pattern="^(score|size|views)$"),
    quality: str | None = Query(None, pattern="^(4k|1080p|720p)$"),
    db: Session = Depends(get_db),
):
    media = db.query(Media).filter(Media.tmdb_id == tmdb_id).first()
    if not media:
        return {"success": True, "media": None, "data": [], "total": 0, "message": "暂无资源"}

    q = db.query(Resource).filter(Resource.media_id == media.id)
    if quality:
        q = q.filter(Resource.resolution.ilike(f"%{quality.upper()}%"))
    if sort == "score":
        q = q.order_by(Resource.overall_score.desc())
    elif sort == "size":
        q = q.order_by(Resource.total_size_gb.desc())
    elif sort == "views":
        q = q.order_by(Resource.views.desc())
    items = q.all()
    items, invalid_count = await _filter_valid_resources(items)
    message = "未找到可用资源" if not items else ""
    return {
        "success": True,
        "media": media,
        "data": [_resource_payload(r) for r in items],
        "total": len(items),
        "message": message,
        "invalid_count": invalid_count,
    }

