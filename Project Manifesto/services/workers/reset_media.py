#!/usr/bin/env python3
import asyncio
from sqlalchemy import select

from app.core.db import AsyncSessionLocal, init_db
from app.models.media import TaskStatus, VirtualMedia

async def main() -> None:
    media_id = 1  # 测试用的 media_id
    await init_db()
    async with AsyncSessionLocal() as session:
        media = await session.get(VirtualMedia, media_id)
        if media:
            print(f"当前状态: task_status={media.task_status.value if media.task_status else 'N/A'}, retry_count={media.retry_count}")
            print(f"错误信息: {media.error_message or '无'}")
            
            # 重置任务状态
            media.task_status = TaskStatus.pending
            media.retry_count = 0
            media.error_message = None
            media.task_id = None
            media.last_retry_at = None
            await session.commit()
            print("任务状态已重置为 pending")
        else:
            print("未找到 media")

if __name__ == "__main__":
    asyncio.run(main())
