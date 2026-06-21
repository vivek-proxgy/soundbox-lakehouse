from __future__ import annotations

from enum import StrEnum


class ReadinessCheck(StrEnum):
    """Readiness probe check identifiers."""

    AUTH_API_KEY = "auth_api_key"
    GEMINI_API_KEY = "gemini_api_key"
    PARQUET_DATA = "parquet_data"

    @classmethod
    def critical_checks(cls) -> frozenset[str]:
        return frozenset({cls.AUTH_API_KEY, cls.GEMINI_API_KEY, cls.PARQUET_DATA})
