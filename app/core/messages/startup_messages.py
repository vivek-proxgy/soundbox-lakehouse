from __future__ import annotations

from enum import StrEnum


class ReadinessMessage(StrEnum):
    AUTH_API_KEY_REQUIRED = "{env} is required when AUTH_ENABLED=true"
    GEMINI_API_KEY_REQUIRED = "{env} is required for intelligence routes"
    PARQUET_DATA_MISSING = (
        "No parquet data found — run ingestion or configure GCS warehouse paths"
    )


class StartupMessage(StrEnum):
    VALIDATION_FAILED = "Intelligence API startup validation failed. Missing: {missing}"
    AUTH_API_KEY_ONLY_JWT_IGNORED = (
        "AUTH_API_KEY_ONLY=true — JWT auth is disabled; {env} is ignored"
    )
    API_KEY_TOO_SHORT = (
        "{env} is shorter than {min_length} characters — use a strong secret in production"
    )
    UNSUPPORTED_RUN_MODE = (
        "Unsupported RUN_MODE={mode!r} — must be one of: {allowed}"
    )
