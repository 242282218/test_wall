"""
全局错误处理器
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.quark.logger import logger
from app.quark.utils.exceptions import (
    QuarkSearchException,
    TMDBException,
    QuarkAPIException,
    DatabaseException,
    ValidationException,
    NotFoundException
)


async def quark_search_exception_handler(
    request: Request,
    exc: QuarkSearchException
) -> JSONResponse:
    """夸克搜索服务异常处理器"""
    logger.error(
        f"服务异常: {exc.code} - {exc.message}",
        extra={"path": request.url.path, "method": request.method}
    )
    
    status_code_map = {
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
        "DATABASE_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "TMDB_ERROR": status.HTTP_502_BAD_GATEWAY,
        "QUARK_ERROR": status.HTTP_502_BAD_GATEWAY,
    }
    
    http_status = status_code_map.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return JSONResponse(
        status_code=http_status,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message
            }
        }
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """请求验证异常处理器"""
    logger.warning(
        f"请求验证失败: {exc.errors()}",
        extra={"path": request.url.path, "method": request.method}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数验证失败",
                "details": exc.errors()
            }
        }
    )


async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """通用异常处理器"""
    logger.exception(
        f"未处理的异常: {type(exc).__name__} - {str(exc)}",
        extra={"path": request.url.path, "method": request.method}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "服务器内部错误"
            }
        }
    )

