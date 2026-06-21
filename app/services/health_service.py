"""Readiness probes for the Intelligence API."""

from __future__ import annotations

from pathlib import Path

from app.config.enums.env_var import SettingsEnv
from app.config.settings import Settings
from app.core.enums.readiness_check import ReadinessCheck
from app.core.messages.startup_messages import ReadinessMessage


def _parquet_available(settings: Settings) -> bool:
    if settings.upload_to_gcs and settings.warehouse_uri.startswith("gs://"):
        return bool(settings.gcs_bucket or settings.warehouse_path)
    root = Path(settings.lakehouse_local_root)
    if not root.exists():
        return False
    return any(root.glob("**/*.parquet"))


def build_readiness_report(settings: Settings) -> dict[str, str | bool | list[str]]:
    """Deep readiness check — used by Cloud Run startup/readiness probes."""
    checks: dict[str, bool] = {}
    issues: list[str] = []

    if settings.auth_enabled:
        checks[ReadinessCheck.AUTH_API_KEY] = bool(settings.lakehouse_api_key)
        if not checks[ReadinessCheck.AUTH_API_KEY]:
            issues.append(
                ReadinessMessage.AUTH_API_KEY_REQUIRED.format(
                    env=SettingsEnv.LAKEHOUSE_API_KEY,
                )
            )
    else:
        checks[ReadinessCheck.AUTH_API_KEY] = True

    checks[ReadinessCheck.GEMINI_API_KEY] = bool(settings.gemini_api_key)
    if not checks[ReadinessCheck.GEMINI_API_KEY]:
        issues.append(
            ReadinessMessage.GEMINI_API_KEY_REQUIRED.format(env=SettingsEnv.GEMINI_API_KEY)
        )

    checks[ReadinessCheck.PARQUET_DATA] = _parquet_available(settings)
    if not checks[ReadinessCheck.PARQUET_DATA]:
        issues.append(ReadinessMessage.PARQUET_DATA_MISSING)

    ready = all(checks[name] for name in ReadinessCheck.critical_checks())

    return {
        "status": "ready" if ready else "not_ready",
        "service": "soundbox-intelligence",
        "checks": checks,
        "issues": issues,
    }
