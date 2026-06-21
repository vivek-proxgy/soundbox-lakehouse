"""Fail-fast validation when starting the Intelligence API server."""

from __future__ import annotations

import logging

from app.config.enums.env_var import SettingsEnv
from app.config.settings import Settings
from app.core.constants.api_key import ApiKeyPolicy
from app.core.enums.run_mode import RunMode
from app.core.messages.startup_messages import StartupMessage

logger = logging.getLogger(__name__)


def validate_server_startup(settings: Settings) -> None:
    """Raise on missing production-critical configuration."""
    if settings.run_mode != RunMode.SERVER:
        return

    missing: list[str] = []

    if settings.auth_enabled and not settings.lakehouse_api_key:
        missing.append(SettingsEnv.LAKEHOUSE_API_KEY)

    if not settings.gemini_api_key:
        missing.append(SettingsEnv.GEMINI_API_KEY)

    if settings.auth_api_key_only and settings.auth_jwt_secret:
        logger.warning(
            StartupMessage.AUTH_API_KEY_ONLY_JWT_IGNORED.format(
                env=SettingsEnv.AUTH_JWT_SECRET,
            )
        )

    if missing:
        raise RuntimeError(
            StartupMessage.VALIDATION_FAILED.format(missing=", ".join(missing))
        )

    if len(settings.lakehouse_api_key) < ApiKeyPolicy.MIN_LENGTH:
        logger.warning(
            StartupMessage.API_KEY_TOO_SHORT.format(
                env=SettingsEnv.LAKEHOUSE_API_KEY,
                min_length=ApiKeyPolicy.MIN_LENGTH,
            )
        )
