from __future__ import annotations

from enum import StrEnum


class SettingsEnv(StrEnum):
    """Environment variable names — single source of truth for settings and validation."""

    RUN_MODE = "RUN_MODE"
    PORT = "PORT"
    SERVER_HOST = "SERVER_HOST"
    LOG_LEVEL = "LOG_LEVEL"
    AUTH_ENABLED = "AUTH_ENABLED"
    AUTH_API_KEY_ONLY = "AUTH_API_KEY_ONLY"
    AUTH_JWT_SECRET = "AUTH_JWT_SECRET"
    LAKEHOUSE_API_KEY = "LAKEHOUSE_API_KEY"
    GEMINI_API_KEY = "GEMINI_API_KEY"
    INTEGRATION_TEST = "INTEGRATION_TEST"
    LAKEHOUSE_BASE_URL = "LAKEHOUSE_BASE_URL"
