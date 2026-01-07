import asyncio
import json
import logging
import os
import posixpath
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import redis.asyncio as redis
from sqlalchemy.exc import SQLAlchemyError
from tenacity import retry, stop_after_attempt, wait_exponential


ROOT = Path(__file__).resolve().parents[2]
CORE_BACKEND = ROOT / "services" / "core-backend"
if CORE_BACKEND.exists() and str(CORE_BACKEND) not in sys.path:
    sys.path.append(str(CORE_BACKEND))

from app.core.db import AsyncSessionLocal, init_db  # noqa: E402
from app.models.media import TaskStatus, VirtualMedia  # noqa: E402
try:  # noqa: E402
    from .quark_client import QuarkClient, QuarkAuthError, QuarkNetworkError, QuarkAPIError  # type: ignore
    from .media_classifier import MediaClassifier  # type: ignore
    from .cookie_manager import CookieManager  # type: ignore
except ImportError:  # pragma: no cover - supports direct script execution
    from quark_client import QuarkClient, QuarkAuthError, QuarkNetworkError, QuarkAPIError  # type: ignore
    from media_classifier import MediaClassifier  # type: ignore
    from cookie_manager import CookieManager  # type: ignore


QUEUE_KEY = os.getenv("TRANSFER_QUEUE_KEY", "queue:transfer")
DEAD_QUEUE_KEY = os.getenv("TRANSFER_DEAD_QUEUE_KEY", "queue:transfer:dead")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
WEBDAV_CACHE_URL = os.getenv(
    "WEBDAV_CACHE_URL",
    "http://quarkdrive-webdav:12345/cache/invalidate",
)
HTTP_TIMEOUT = float(os.getenv("TRANSFER_HTTP_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("TRANSFER_MAX_RETRIES", "3"))

logger = logging.getLogger("transfer_worker")


async def refresh_webdav_cache(client: httpx.AsyncClient) -> None:
    response = await client.post(WEBDAV_CACHE_URL, json={"path": "/"})
    response.raise_for_status()


async def handle_task(
    payload: Dict[str, Any],
    http_client: httpx.AsyncClient,
    quark_client: QuarkClient,
    classifier: MediaClassifier,
    redis_client: redis.Redis,
) -> Optional[str]:
    media_id = payload.get("media_id")
    if media_id is None:
        logger.warning("task missing media_id: %s", payload)
        return None

    retry_count = payload.get("retry_count", 0)
    
    async with AsyncSessionLocal() as session:
        media = await session.get(VirtualMedia, int(media_id))
        if not media:
            logger.warning("media not found: %s", media_id)
            return None
        if media.is_archived:
            logger.info("media already archived: %s", media_id)
            return None
        
        media.task_status = TaskStatus.processing
        media.task_id = payload.get("task_id")
        media.retry_count = retry_count
        media.last_retry_at = datetime.utcnow()
        media.error_message = None

        try:
            share_url = payload.get("share_url") or media.share_url
            share_fid_token = payload.get("share_fid_token") or media.share_fid_token
            original_fid = payload.get("original_fid") or media.original_fid
            virtual_path = payload.get("virtual_path") or media.virtual_path
            file_name = posixpath.basename(virtual_path) if virtual_path else None
            if not share_url or not share_fid_token:
                raise ValueError("missing share_url or share_fid_token")

            logger.info("processing media %s (retry %d/%d)", media_id, retry_count, MAX_RETRIES)
            logger.info("getting stoken for media %s", media_id)
            stoken = await quark_client.get_stoken(share_url)

            dest_path = classifier.build_dest_path(
                title=media.title,
                filename=file_name or "",
            )
            logger.info("destination path: %s", dest_path)

            cached_fid = classifier.get_cached_dir_fid(dest_path)
            if not cached_fid:
                logger.info("creating directory: %s", dest_path)
                cached_fid = await quark_client.get_or_create_dir(dest_path)
                classifier.cache_dir_fid(dest_path, cached_fid)

            logger.info("saving share for media %s", media_id)
            saved = await quark_client.share_save(
                share_fid_token,
                stoken,
                cached_fid,
                share_url=share_url,
                file_fid=original_fid,
            )
            if not saved:
                raise QuarkAPIError("share_save returned False")

            await refresh_webdav_cache(http_client)

            if file_name:
                physical_path = f"{dest_path.rstrip('/')}/{file_name}"
            else:
                physical_path = dest_path
            media.physical_path = physical_path
            media.is_archived = True
            media.task_status = TaskStatus.completed
            media.error_message = None
            media.updated_at = datetime.utcnow()
            logger.info("media %s archived successfully to %s", media_id, physical_path)

            await session.commit()
            return cached_fid
        except QuarkAuthError as exc:
            await session.rollback()
            media.task_status = TaskStatus.failed
            media.error_message = f"Authentication error: {str(exc)}"
            media.updated_at = datetime.utcnow()
            logger.error("authentication error for media %s: %s", media_id, exc)
            try:
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
            raise
        except QuarkNetworkError as exc:
            await session.rollback()
            media.task_status = TaskStatus.failed
            media.error_message = f"Network error: {str(exc)}"
            media.updated_at = datetime.utcnow()
            logger.warning("network error for media %s (retry %d): %s", media_id, retry_count, exc)
            try:
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
            raise
        except QuarkAPIError as exc:
            await session.rollback()
            media.task_status = TaskStatus.failed
            media.error_message = f"API error: {str(exc)}"
            media.updated_at = datetime.utcnow()
            logger.error("API error for media %s: %s", media_id, exc)
            try:
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
            raise
        except httpx.HTTPStatusError as exc:
            await session.rollback()
            media.task_status = TaskStatus.failed
            media.error_message = f"HTTP error: {str(exc)}"
            media.updated_at = datetime.utcnow()
            logger.warning("HTTP error for media %s: %s", media_id, exc)
            try:
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
            raise
        except Exception as exc:
            try:
                await session.rollback()
            except SQLAlchemyError:
                pass
            media.task_status = TaskStatus.failed
            media.error_message = f"Unexpected error: {str(exc)}"
            media.updated_at = datetime.utcnow()
            try:
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
            logger.exception("task failed for media %s: %s", media_id, exc)
            raise


async def worker_loop() -> None:
    logging.basicConfig(
        level=os.getenv("TRANSFER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("transfer worker started, queue=%s", QUEUE_KEY)
    logger.info("dead letter queue=%s, max_retries=%d", DEAD_QUEUE_KEY, MAX_RETRIES)

    await init_db()

    cookie = os.getenv("QUARK_COOKIE", "")
    if not cookie:
        raise RuntimeError("QUARK_COOKIE is required for transfer worker")

    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    cookie_manager = CookieManager(cookie)
    quark_client = QuarkClient(cookie_manager.cookie)
    classifier = MediaClassifier()

    try:
        await cookie_manager.validate_cookie(quark_client)
        
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            while True:
                try:
                    if cookie_manager.needs_validation():
                        is_valid = await cookie_manager.validate_cookie(quark_client)
                        if not is_valid:
                            logger.error("cookie validation failed, worker will continue but may fail on API calls")
                    
                    _, raw = await redis_client.blpop(QUEUE_KEY)
                    payload = json.loads(raw)
                    
                    try:
                        await handle_task(
                            payload,
                            client,
                            quark_client,
                            classifier,
                            redis_client,
                        )
                    except (QuarkNetworkError, httpx.TimeoutException, httpx.TransportError) as exc:
                        retry_count = payload.get("retry_count", 0)
                        if retry_count < MAX_RETRIES:
                            payload["retry_count"] = retry_count + 1
                            await redis_client.rpush(QUEUE_KEY, json.dumps(payload))
                            logger.warning("task queued for retry %d/%d: media_id=%s", 
                                         retry_count + 1, MAX_RETRIES, payload.get("media_id"))
                        else:
                            await redis_client.rpush(DEAD_QUEUE_KEY, json.dumps(payload))
                            logger.error("task moved to dead queue after %d retries: media_id=%s, error=%s",
                                       MAX_RETRIES, payload.get("media_id"), exc)
                    except QuarkAuthError as exc:
                        await redis_client.rpush(DEAD_QUEUE_KEY, json.dumps(payload))
                        logger.error("authentication error, task moved to dead queue: media_id=%s, error=%s",
                                   payload.get("media_id"), exc)
                        await cookie_manager.validate_cookie(quark_client)
                    except Exception as exc:
                        await redis_client.rpush(DEAD_QUEUE_KEY, json.dumps(payload))
                        logger.exception("unexpected error, task moved to dead queue: media_id=%s, error=%s",
                                      payload.get("media_id"), exc)
                    
                    await asyncio.sleep(0.1)
                except json.JSONDecodeError as exc:
                    logger.warning("invalid task payload: %s", exc)
                except Exception as exc:
                    logger.exception("worker loop error: %s", exc)
                    await asyncio.sleep(1)
    finally:
        await quark_client.close()
        await redis_client.close()


if __name__ == "__main__":
    asyncio.run(worker_loop())
