"""
自定义异常类
"""
from typing import Optional


class QuarkSearchException(Exception):
    """基础异常类"""
    
    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        super().__init__(self.message)


class TMDBException(QuarkSearchException):
    """TMDB API 异常"""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        code = f"TMDB_ERROR_{status_code}" if status_code else "TMDB_ERROR"
        super().__init__(message, code)


class QuarkAPIException(QuarkSearchException):
    """夸克 API 异常"""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        code = f"QUARK_ERROR_{status_code}" if status_code else "QUARK_ERROR"
        super().__init__(message, code)


class DatabaseException(QuarkSearchException):
    """数据库异常"""
    
    def __init__(self, message: str):
        super().__init__(message, "DATABASE_ERROR")


class ValidationException(QuarkSearchException):
    """验证异常"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        code = f"VALIDATION_ERROR_{field}" if field else "VALIDATION_ERROR"
        super().__init__(message, code)


class NotFoundException(QuarkSearchException):
    """资源未找到异常"""
    
    def __init__(self, resource_type: str, resource_id: Optional[str] = None):
        message = f"{resource_type} not found"
        if resource_id:
            message += f": {resource_id}"
        super().__init__(message, "NOT_FOUND")

