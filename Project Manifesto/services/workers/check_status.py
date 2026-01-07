#!/usr/bin/env python3
import asyncio
import sys
from sqlalchemy import select

from app.core.db import AsyncSessionLocal, init_db
from app.models.media import VirtualMedia

async def main() -> None:
    media_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    
    await init_db()
    async with AsyncSessionLocal() as session:
        media = await session.get(VirtualMedia, media_id)
        if media:
            status = media.task_status.value if media.task_status else 'N/A'
            archived = media.is_archived
            path = media.physical_path or 'N/A'
            error = media.error_message or '无'
            retry = media.retry_count
            
            print(f"任务状态: {status}")
            print(f"已归档: {archived}")
            print(f"物理路径: {path}")
            print(f"重试次数: {retry}")
            print(f"错误信息: {error}")
        else:
            print("未找到 media")

if __name__ == "__main__":
    asyncio.run(main())
