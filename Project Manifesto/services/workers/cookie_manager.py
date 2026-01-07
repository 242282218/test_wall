import logging
import os
import time
from datetime import datetime
from typing import Optional


logger = logging.getLogger("cookie_manager")


class CookieManager:
    def __init__(self, cookie: Optional[str] = None):
        self._cookie = cookie or os.getenv("QUARK_COOKIE", "")
        self._last_validated: Optional[datetime] = None
        self._is_valid: bool = True
        self._validation_interval = int(os.getenv("COOKIE_VALIDATION_INTERVAL", "3600"))
        self._audit_log = []

    @property
    def cookie(self) -> str:
        return self._cookie

    def update_cookie(self, new_cookie: str) -> None:
        old_cookie = self._cookie
        self._cookie = new_cookie
        self._last_validated = None
        self._is_valid = True
        logger.info("cookie updated (length: %d -> %d)", len(old_cookie), len(new_cookie))
        self._log_audit("cookie_updated", {"old_length": len(old_cookie), "new_length": len(new_cookie)})

    async def validate_cookie(self, quark_client) -> bool:
        if not self._cookie:
            logger.error("cookie is empty")
            self._is_valid = False
            return False

        now = datetime.utcnow()
        if (self._last_validated and 
            (now - self._last_validated).total_seconds() < self._validation_interval):
            return self._is_valid

        try:
            logger.info("validating cookie...")
            await quark_client._get_config()
            self._is_valid = True
            self._last_validated = now
            logger.info("cookie validation successful")
            self._log_audit("cookie_validated", {"status": "success"})
            return True
        except Exception as exc:
            self._is_valid = False
            self._last_validated = now
            logger.error("cookie validation failed: %s", exc)
            self._log_audit("cookie_validated", {"status": "failed", "error": str(exc)})
            return False

    def is_valid(self) -> bool:
        return self._is_valid and bool(self._cookie)

    def needs_validation(self) -> bool:
        if not self._last_validated:
            return True
        elapsed = (datetime.utcnow() - self._last_validated).total_seconds()
        return elapsed >= self._validation_interval

    def get_audit_log(self, limit: int = 100) -> list:
        return self._audit_log[-limit:]

    def _log_audit(self, action: str, details: dict) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details,
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-500:]
        logger.debug("audit log: %s", entry)