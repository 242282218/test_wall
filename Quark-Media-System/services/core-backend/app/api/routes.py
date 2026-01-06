import json
import os
import re
from typing import Iterable, Optional, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.media import TaskStatus, VirtualMedia
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

share_router = APIRouter(prefix="/api/v1/share", tags=["share"])
media_router = APIRouter(prefix="/api/v1/media", tags=["media"])
task_router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
resources_router = APIRouter(prefix="/api/v1/resources", tags=["resources"])
legacy_resources_router = APIRouter(prefix="/api", tags=["resources"])

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


@media_router.post("/{media_id}/provision")
async def provision_media(
    media_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(VirtualMedia).where(VirtualMedia.id == media_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    if media.is_archived:
        return {"status": "archived", "physical_path": media.physical_path}

    if media.task_status == TaskStatus.processing:
        return {"status": "processing", "message": "Provisioning already in progress"}

    media.task_status = TaskStatus.processing
    media.task_id = None
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
        media.task_status = TaskStatus.failed
        media.error_message = f"Failed to enqueue: {str(exc)}"
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue transfer task",
        ) from exc

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "accepted", "message": "Provisioning started"},
    )


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
router.include_router(media_router)
router.include_router(task_router)
router.include_router(resources_router)
router.include_router(legacy_resources_router)
