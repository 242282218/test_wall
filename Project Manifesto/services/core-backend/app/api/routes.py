import hashlib
import json
import os
import re
from datetime import datetime
from typing import Iterable, Optional, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
import redis.asyncio as redis
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.media import TaskStatus, VirtualMedia
from app.schemas.media import (
    HomeFeedResponse,
    MediaDetailResponse,
    MediaItem,
    MediaResourceItem,
    ProvisionRequest,
    SaveVirtualLinkRequest,
    SaveVirtualLinkResponse,
    TaskRecordResponse,
)
from app.schemas.resources import ChannelInfo, ResourceSearchResponse
from app.schemas.share import ShareParseRequest, ShareParseResponse
from app.services.share_parser import (
    QuarkShareAuthError,
    QuarkShareNotFoundError,
    QuarkShareParser,
    QuarkShareError,
)
from app.services.telegram_searcher import get_channels, searcher

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".mpg",
    ".mpeg",
    ".m4v",
    ".ts",
    ".rmvb",
}
LARGE_FILE_BYTES = 1_073_741_824
VIRTUAL_MEDIA_ROOT = "/Movies"
UNKNOWN_TMDB_ID = 0
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
TRANSFER_QUEUE_KEY = os.getenv("TRANSFER_QUEUE_KEY", "queue:transfer")
DEAD_QUEUE_KEY = os.getenv("TRANSFER_DEAD_QUEUE_KEY", "queue:transfer:dead")
HOME_FEED_LIMIT = int(os.getenv("HOME_FEED_LIMIT", "24"))

share_router = APIRouter(prefix="/api/v1/share", tags=["share"])
media_router = APIRouter(prefix="/api/v1/media", tags=["media"])
task_router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
resources_router = APIRouter(prefix="/api/v1/resources", tags=["resources"])
legacy_resources_router = APIRouter(prefix="/api", tags=["resources"])
home_router = APIRouter(prefix="/api/v1", tags=["home"])

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def _get_query_param(request: Request, *names: str) -> Optional[str]:
    for name in names:
        value = request.query_params.get(name)
        if value:
            return value
    return None


def _apply_passcode(url: str, passcode: str) -> str:
    if not passcode:
        return url

    if "://" not in url and "/" not in url:
        return f"https://pan.quark.cn/s/{url}?pwd={passcode}"

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["pwd"] = [passcode]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _extract_share_code(share_url: str) -> str:
    if "://" not in share_url and "/" not in share_url:
        return share_url.strip()

    parsed = urlparse(share_url)
    match = re.search(r"/s/([A-Za-z0-9]+)", parsed.path)
    if match:
        return match.group(1)
    return "share"


def _sanitize_segment(value: str, fallback: str) -> str:
    cleaned = (value or "").strip().strip("/")
    cleaned = cleaned.replace("\\", "_").replace("/", "_")
    return cleaned or fallback


def _resolve_share_title(files: Iterable[dict], share_url: str) -> str:
    top_levels = set()
    for item in files:
        path = item.get("path") or ""
        normalized = path.strip("/")
        if not normalized:
            continue
        top_levels.add(normalized.split("/", 1)[0])

    if len(top_levels) == 1:
        return _sanitize_segment(next(iter(top_levels)), "share")
    return _sanitize_segment(_extract_share_code(share_url), "share")


def _is_video_file(name: str) -> bool:
    _, ext = os.path.splitext(name)
    return ext.lower() in VIDEO_EXTENSIONS


def _is_large_file(size: Optional[int]) -> bool:
    return bool(size and size >= LARGE_FILE_BYTES)


def _should_store_file(item: dict) -> bool:
    if item.get("is_dir"):
        return False
    name = item.get("name") or ""
    if not name:
        return False
    return _is_video_file(name) or _is_large_file(item.get("size"))


def _build_virtual_path(share_title: str, file_name: str) -> str:
    root = VIRTUAL_MEDIA_ROOT.rstrip("/")
    share_segment = _sanitize_segment(share_title, "share")
    file_segment = _sanitize_segment(file_name, "file")
    return f"{root}/{share_segment}/{file_segment}"


def _hash_share_url(share_url: str) -> str:
    if not share_url:
        return "link"
    return hashlib.md5(share_url.encode("utf-8")).hexdigest()[:8]


def _build_virtual_link_path(
    tmdb_id: int,
    title: str,
    link_id: str,
    share_url: str,
) -> str:
    root = VIRTUAL_MEDIA_ROOT.rstrip("/")
    title_segment = _sanitize_segment(title, f"tmdb-{tmdb_id}")
    link_segment = _sanitize_segment(link_id, _hash_share_url(share_url))
    return f"{root}/tmdb-{tmdb_id}/{title_segment}-{link_segment}"


def _map_resource_status(media: VirtualMedia) -> str:
    if media.is_archived or media.task_status == TaskStatus.completed:
        return "MATERIALIZED"
    if media.task_status == TaskStatus.processing:
        return "PROVISIONING"
    if media.task_status == TaskStatus.failed:
        return "FAILED"
    return "VIRTUAL"


def _build_media_item(media: VirtualMedia) -> MediaItem:
    return MediaItem(
        tmdb_id=str(media.tmdb_id),
        title=media.title,
        status=_map_resource_status(media),
        overview=None,
        year=None,
        rating=None,
        poster_url=None,
    )


def _build_resource_item(media: VirtualMedia) -> MediaResourceItem:
    name = media.title or os.path.basename(media.virtual_path or "")
    return MediaResourceItem(
        id=str(media.id or ""),
        name=name or "Untitled",
        status=_map_resource_status(media),
        updated_at=media.updated_at.isoformat() if media.updated_at else None,
        webdav_path=media.physical_path,
        error_message=media.error_message,
    )


def _task_progress(status: TaskStatus) -> Optional[float]:
    if status == TaskStatus.pending:
        return 0.1
    if status == TaskStatus.processing:
        return 0.5
    if status == TaskStatus.completed:
        return 1.0
    if status == TaskStatus.failed:
        return 0.0
    return None


def _build_task_record(media: VirtualMedia, link_id: Optional[str]) -> TaskRecordResponse:
    return TaskRecordResponse(
        task_id=media.task_id or "",
        status=media.task_status.value,
        tmdb_id=str(media.tmdb_id),
        link_id=link_id or None,
        updated_at=media.updated_at.isoformat()
        if media.updated_at
        else datetime.utcnow().isoformat(),
        error_message=media.error_message,
        progress=_task_progress(media.task_status),
        result_webdav_url=media.physical_path,
    )


async def _upsert_virtual_media(
    session: AsyncSession,
    files: Iterable[dict],
    share_url: str,
    share_title: str,
) -> None:
    wrote = False
    for item in files:
        if not _should_store_file(item):
            continue

        file_name = item.get("name") or ""
        virtual_path = _build_virtual_path(share_title, file_name)
        result = await session.execute(
            select(VirtualMedia).where(VirtualMedia.virtual_path == virtual_path)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.share_url = share_url
            existing.original_fid = item.get("fid") or ""
            existing.share_fid_token = item.get("share_fid_token") or ""
        else:
            session.add(
                VirtualMedia(
                    tmdb_id=UNKNOWN_TMDB_ID,
                    title=share_title,
                    share_url=share_url,
                    original_fid=item.get("fid") or "",
                    share_fid_token=item.get("share_fid_token") or "",
                    virtual_path=virtual_path,
                )
            )
        wrote = True

    if not wrote:
        return

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()


@share_router.post("/parse", response_model=ShareParseResponse)
async def parse_share_link(
    payload: ShareParseRequest,
    session: AsyncSession = Depends(get_session),
) -> ShareParseResponse:
    share_url = _apply_passcode(payload.url, payload.passcode or "")
    cookie = os.getenv("QUARK_COOKIE", "")

    try:
        async with QuarkShareParser(cookie=cookie if cookie else None) as parser:
            files = await parser.parse_share_link(share_url)
        share_title = _resolve_share_title(files, share_url)
        await _upsert_virtual_media(session, files, share_url, share_title)
        return ShareParseResponse(total_count=len(files), files=files)
    except QuarkShareAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except QuarkShareNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except QuarkShareError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@home_router.get("/home", response_model=HomeFeedResponse)
async def get_home_feed(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(VirtualMedia).order_by(VirtualMedia.updated_at.desc())
    )
    medias = result.scalars().all()
    favorites: List[MediaItem] = []
    trending: List[MediaItem] = []
    seen_tmdb: set[int] = set()

    for media in medias:
        if media.tmdb_id in seen_tmdb:
            continue
        seen_tmdb.add(media.tmdb_id)
        item = _build_media_item(media)
        if media.is_archived or media.task_status == TaskStatus.completed:
            favorites.append(item)
        else:
            trending.append(item)

    return HomeFeedResponse(
        favorites=favorites[:HOME_FEED_LIMIT],
        trending=trending[:HOME_FEED_LIMIT],
        updated_at=datetime.utcnow().isoformat(),
    )


@media_router.get("/{tmdb_id}", response_model=MediaDetailResponse)
async def get_media_detail(
    tmdb_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(VirtualMedia)
        .where(VirtualMedia.tmdb_id == tmdb_id)
        .order_by(VirtualMedia.updated_at.desc())
    )
    medias = result.scalars().all()
    if not medias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    primary = medias[0]
    resources = [_build_resource_item(media) for media in medias]
    return MediaDetailResponse(
        tmdb_id=str(tmdb_id),
        title=primary.title,
        resources=resources,
    )


@media_router.post("/{tmdb_id}/links/virtual", response_model=SaveVirtualLinkResponse)
async def save_virtual_link(
    tmdb_id: int,
    payload: SaveVirtualLinkRequest,
    session: AsyncSession = Depends(get_session),
):
    if payload.tmdb_id:
        try:
            payload_tmdb_id = int(payload.tmdb_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tmdbId",
            ) from exc
        if payload_tmdb_id != tmdb_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tmdbId mismatch",
            )

    virtual_path = _build_virtual_link_path(
        tmdb_id,
        payload.title,
        payload.link_id,
        payload.share_url,
    )
    result = await session.execute(
        select(VirtualMedia).where(VirtualMedia.virtual_path == virtual_path)
    )
    media = result.scalar_one_or_none()

    if media:
        media.title = payload.title
        media.share_url = payload.share_url
        media.original_fid = payload.link_id or media.original_fid
        media.updated_at = datetime.utcnow()
    else:
        media = VirtualMedia(
            tmdb_id=tmdb_id,
            title=payload.title,
            share_url=payload.share_url,
            original_fid=payload.link_id or "",
            share_fid_token="",
            virtual_path=virtual_path,
            task_status=TaskStatus.pending,
            is_archived=False,
            updated_at=datetime.utcnow(),
        )
        session.add(media)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Virtual link already exists",
        )

    return SaveVirtualLinkResponse(
        status="VIRTUAL",
        saved_at=datetime.utcnow().isoformat(),
    )


@media_router.post("/{tmdb_id}/provision", response_model=TaskRecordResponse)
async def provision_media(
    tmdb_id: int,
    payload: ProvisionRequest,
    session: AsyncSession = Depends(get_session),
):
    if payload.tmdb_id:
        try:
            payload_tmdb_id = int(payload.tmdb_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tmdbId",
            ) from exc
        if payload_tmdb_id != tmdb_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tmdbId mismatch",
            )

    query = select(VirtualMedia).where(VirtualMedia.tmdb_id == tmdb_id)
    if payload.share_url:
        query = query.where(VirtualMedia.share_url == payload.share_url)
    elif payload.link_id:
        query = query.where(VirtualMedia.original_fid == payload.link_id)

    result = await session.execute(query.order_by(VirtualMedia.updated_at.desc()))
    media = result.scalars().first()
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    link_id = payload.link_id or media.original_fid
    if media.is_archived:
        return _build_task_record(media, link_id)

    if media.task_status == TaskStatus.processing:
        return _build_task_record(media, link_id)

    task_id = media.task_id or f"task_{uuid4().hex[:12]}"
    media.task_status = TaskStatus.processing
    media.task_id = task_id
    media.retry_count = 0
    media.error_message = None
    media.updated_at = datetime.utcnow()
    await session.commit()

    payload_data = {
        "media_id": media.id,
        "share_url": media.share_url,
        "share_fid_token": media.share_fid_token,
        "original_fid": media.original_fid,
        "virtual_path": media.virtual_path,
        "retry_count": 0,
        "task_id": task_id,
    }

    try:
        await redis_client.lpush(TRANSFER_QUEUE_KEY, json.dumps(payload_data))
    except redis.RedisError as exc:
        media.task_status = TaskStatus.failed
        media.error_message = f"Failed to enqueue: {str(exc)}"
        media.updated_at = datetime.utcnow()
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue transfer task",
        ) from exc

    return _build_task_record(media, link_id)


@task_router.get("/stats")
async def get_task_stats(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(VirtualMedia.task_status, 
               func.count(VirtualMedia.id).label("count"))
        .group_by(VirtualMedia.task_status)
    )
    stats = {row.task_status: row.count for row in result}
    
    queue_size = await redis_client.llen(TRANSFER_QUEUE_KEY)
    dead_queue_size = await redis_client.llen(DEAD_QUEUE_KEY)
    
    return {
        "by_status": stats,
        "queue_size": queue_size,
        "dead_queue_size": dead_queue_size,
    }


@task_router.post("/dead/retry/{media_id}")
async def retry_dead_task(
    media_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(VirtualMedia).where(VirtualMedia.id == media_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    
    media.task_status = TaskStatus.pending
    media.retry_count = 0
    media.error_message = None
    await session.commit()
    
    payload = {
        "media_id": media.id,
        "share_url": media.share_url,
        "share_fid_token": media.share_fid_token,
        "original_fid": media.original_fid,
        "virtual_path": media.virtual_path,
        "retry_count": 0,
    }
    
    try:
        await redis_client.lpush(TRANSFER_QUEUE_KEY, json.dumps(payload))
    except redis.RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue retry task",
        ) from exc
    
    return {"status": "queued", "message": "Task requeued for retry"}


@task_router.get("/dead")
async def list_dead_tasks():
    try:
        dead_tasks = await redis_client.lrange(DEAD_QUEUE_KEY, 0, -1)
        return {
            "count": len(dead_tasks),
            "tasks": [json.loads(task) for task in dead_tasks]
        }
    except redis.RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dead queue",
        ) from exc


@task_router.delete("/dead")
async def clear_dead_tasks():
    try:
        count = await redis_client.delete(DEAD_QUEUE_KEY)
        return {"status": "cleared", "count": count}
    except redis.RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear dead queue",
        ) from exc


@task_router.post("/cookie/update")
async def update_cookie(request: dict):
    new_cookie = request.get("cookie")
    if not new_cookie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cookie is required",
        )
    
    os.environ["QUARK_COOKIE"] = new_cookie
    return {"status": "updated", "message": "Cookie updated successfully"}


@task_router.get("/cookie/validate")
async def validate_cookie():
    cookie = os.getenv("QUARK_COOKIE", "")
    if not cookie:
        return {"valid": False, "message": "Cookie is empty"}
    
    try:
        from app.services.share_parser import QuarkShareParser
        async with QuarkShareParser(cookie=cookie) as parser:
            await parser._fetch_share_token("test", "")
        return {"valid": True, "message": "Cookie is valid"}
    except Exception as exc:
        return {"valid": False, "message": str(exc)}


@task_router.get("/{task_id}", response_model=TaskRecordResponse)
async def get_task_status(
    task_id: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(VirtualMedia).where(VirtualMedia.task_id == task_id)
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _build_task_record(media, media.original_fid)


async def _run_resource_search(request: Request, keyword: str) -> ResourceSearchResponse:
    channel_id = _get_query_param(request, "channelId", "channel_id")
    last_message_id = _get_query_param(request, "lastMessageId", "last_message_id")
    results = await searcher.search_all(keyword, channel_id, last_message_id)
    return ResourceSearchResponse(data=results)


@resources_router.get("/search", response_model=ResourceSearchResponse)
async def search_resources(request: Request, keyword: str = "") -> ResourceSearchResponse:
    return await _run_resource_search(request, keyword)


@legacy_resources_router.get("/search", response_model=ResourceSearchResponse)
async def search_resources_legacy(request: Request, keyword: str = "") -> ResourceSearchResponse:
    return await _run_resource_search(request, keyword)


@resources_router.get("/channels", response_model=List[ChannelInfo])
async def list_resource_channels() -> List[ChannelInfo]:
    channels = get_channels()
    return [
        ChannelInfo(id=item["id"], name=item["name"], channel_id=item["id"])
        for item in channels
    ]


router = APIRouter()
router.include_router(share_router)
router.include_router(home_router)
router.include_router(media_router)
router.include_router(task_router)
router.include_router(resources_router)
router.include_router(legacy_resources_router)
