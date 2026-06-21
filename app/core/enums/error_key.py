from __future__ import annotations

from enum import StrEnum


class ErrorKey(StrEnum):
    """Error field keys in API response envelope — matches backend errors map."""

    ERROR = "error"
    VALIDATION = "validation"
    AUTH = "auth"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "notFound"
    CONFLICT = "conflict"
    RATE_LIMIT = "rateLimit"
    SQL = "sql"
    SERVICE = "service"
    CONFIG = "config"
    BODY = "body"
