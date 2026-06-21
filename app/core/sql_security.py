"""Read-only SQL guard shared by intelligence, copilot, and SQL endpoints."""

from __future__ import annotations

import re

from app.config.settings import get_settings
from app.core.enums.error_key import ErrorKey
from app.core.http_errors import bad_request
from app.core.messages.error_messages import ErrorMessage
from app.core.sql.enums.forbidden_keyword import SqlForbiddenKeyword


def sanitize_sql(sql: str) -> str:
    """Validate SQL is read-only and within size limits. Returns cleaned SQL."""
    settings = get_settings()
    max_length = settings.sql_max_length

    if not sql or not sql.strip():
        raise bad_request(ErrorKey.SQL, ErrorMessage.SQL_EMPTY.value)

    if len(sql) > max_length:
        raise bad_request(
            ErrorKey.SQL,
            ErrorMessage.SQL_MAX_LENGTH.value.format(max_length=max_length),
        )

    clean = sql.strip().rstrip(";")
    upper = clean.upper()

    for token in SqlForbiddenKeyword.all_keywords():
        if re.search(rf"\b{token}\b", upper):
            raise bad_request(
                ErrorKey.SQL,
                ErrorMessage.SQL_FORBIDDEN_KEYWORD.value.format(keyword=token),
            )

    if not upper.startswith("SELECT") and not upper.startswith("WITH"):
        raise bad_request(ErrorKey.SQL, ErrorMessage.SQL_SELECT_ONLY.value)

    return clean


def sanitize_org_id(org_id: str | None) -> str | None:
    """Strip unsafe characters from org_id before SQL interpolation."""
    if org_id is None:
        return None
    cleaned = re.sub(r"[^a-zA-Z0-9\-_]", "", org_id.strip())
    return cleaned or None
