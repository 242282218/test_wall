"""
网盘重命名占位：
- POST /rename
需 enable_quark_rename 开关，实际调用夸克网盘客户端。
"""
from fastapi import APIRouter, Depends, HTTPException

from app.quark.deps import get_settings_dep

router = APIRouter(tags=["rename"])


@router.post("/rename")
async def rename_file(payload: dict, settings=Depends(get_settings_dep)):
    if not settings.enable_quark_rename:
        raise HTTPException(status_code=403, detail="rename disabled")
    # TODO: 调用夸克网盘客户端执行重命名
    return {"success": True, "message": "stub"}

