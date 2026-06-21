"""Tests for main entrypoint server settings."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.config.enums.env_var import SettingsEnv
from app.config.settings import get_settings
from app.core.enums.run_mode import DEFAULT_BIND_HOST, RunMode, ServerDefaults
from main import run_for_mode


def test_settings_server_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(SettingsEnv.RUN_MODE, RunMode.INGEST)
    monkeypatch.delenv(SettingsEnv.SERVER_HOST, raising=False)
    monkeypatch.delenv(SettingsEnv.PORT, raising=False)
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.server_host == DEFAULT_BIND_HOST
    assert settings.server_port == ServerDefaults.PORT

    get_settings.cache_clear()


def test_settings_server_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(SettingsEnv.RUN_MODE, RunMode.SERVER)
    monkeypatch.setenv(SettingsEnv.SERVER_HOST, "127.0.0.1")
    monkeypatch.setenv(SettingsEnv.PORT, "9090")
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.server_host == "127.0.0.1"
    assert settings.server_port == 9090

    get_settings.cache_clear()


def test_run_for_mode_rejects_unknown_mode():
    settings = Mock(run_mode="batch")

    with pytest.raises(RuntimeError, match="Unsupported RUN_MODE"):
        run_for_mode(settings)
