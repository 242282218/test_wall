#!/usr/bin/env python3
import asyncio
from sqlalchemy import select

from app.core.db import AsyncSessionLocal, init_db
from app.models.media import VirtualMedia

async def main() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        stmt = select(VirtualMedia).order_by(VirtualMedia.id.desc()).limit(5)
        result = await session.execute(stmt)
        media_list = result.scalars().all()
        for media in media_list:
            title = media.title[:50] if media.title else "N/A"
            status = media.task_status.value if media.task_status else "N/A"
            url = media.share_url[:80] if media.share_url else "N/A"
            print(f"ID: {media.id}, Title: {title}..., Status: {status}, URL: {url}...")

if __name__ == "__main__":
    asyncio.run(main())
