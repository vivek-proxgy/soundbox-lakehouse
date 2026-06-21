"""Tests for explicit RUN_MODE configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config.enums.env_var import SettingsEnv
from app.config.settings import Settings, get_settings
from app.core.enums.run_mode import RunMode
from app.core.startup_validation import validate_server_startup


def test_run_mode_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(SettingsEnv.RUN_MODE, raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValidationError, match=SettingsEnv.RUN_MODE):
        get_settings()

    get_settings.cache_clear()


def test_run_mode_rejects_invalid_value(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(SettingsEnv.RUN_MODE, "batch")
    get_settings.cache_clear()

    with pytest.raises(ValidationError, match="invalid"):
        get_settings()

    get_settings.cache_clear()


def test_run_mode_accepts_server_and_ingest(monkeypatch: pytest.MonkeyPatch):
    for mode in (RunMode.SERVER, RunMode.INGEST):
        monkeypatch.setenv(SettingsEnv.RUN_MODE, mode)
        get_settings.cache_clear()
        assert get_settings().run_mode == mode

    get_settings.cache_clear()


def test_validate_server_startup_skips_ingest_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(SettingsEnv.RUN_MODE, RunMode.INGEST)
    monkeypatch.delenv(SettingsEnv.GEMINI_API_KEY, raising=False)
    get_settings.cache_clear()

    validate_server_startup(get_settings())

    get_settings.cache_clear()


def test_validate_server_startup_requires_keys_in_server_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(SettingsEnv.RUN_MODE, RunMode.SERVER)
    monkeypatch.setenv(SettingsEnv.AUTH_ENABLED, "true")
    monkeypatch.delenv(SettingsEnv.LAKEHOUSE_API_KEY, raising=False)
    monkeypatch.delenv(SettingsEnv.GEMINI_API_KEY, raising=False)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match=SettingsEnv.LAKEHOUSE_API_KEY):
        validate_server_startup(get_settings())

    get_settings.cache_clear()
