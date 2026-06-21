"""Safe execution helper — mirrors on-prem-soundbox-backend controller try/catch."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from fastapi import HTTPException

from app.core.enums.error_key import ErrorKey
from app.core.http_errors import bad_request
from app.core.messages.error_messages import ErrorMessage

T = TypeVar("T")

logger = logging.getLogger("lakehouse.guard")


def run_safe(
    operation: Callable[[], T],
    *,
    error_key: ErrorKey = ErrorKey.ERROR,
    message: str | None = None,
    log_context: str = "operation",
) -> T:
    """Execute operation; re-raise HTTPException, wrap other errors as 400."""
    try:
        return operation()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("%s failed", log_context, exc_info=exc)
        raise bad_request(
            error_key,
            message or ErrorMessage.GENERIC_FAILURE.value,
        ) from exc
