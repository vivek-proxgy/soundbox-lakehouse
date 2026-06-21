"""Tests for liveness and readiness endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.core.http_status import HttpStatus
from app.server import create_app


@pytest.fixture
def health_client(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("LAKEHOUSE_API_KEY", "a" * 32)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("LAKEHOUSE_LOCAL_ROOT", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(create_app(), raise_server_exceptions=False)
    yield client
    get_settings.cache_clear()


def test_health_liveness(health_client: TestClient):
    response = health_client.get("/health")
    assert response.status_code == HttpStatus.HTTP_200_OK
    body = response.json()
    assert body["status"] == "healthy"
    assert body["auth_configured"] is True


def test_ready_returns_503_when_parquet_missing(health_client: TestClient):
    response = health_client.get("/ready")
    assert response.status_code == HttpStatus.HTTP_503_SERVICE_UNAVAILABLE
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["gemini_api_key"] is True
    assert body["checks"]["parquet_data"] is False


def test_ready_returns_200_when_configured(monkeypatch: pytest.MonkeyPatch, tmp_path):
    data_dir = tmp_path / "merchants"
    data_dir.mkdir()
    (data_dir / "sample.parquet").write_bytes(b"placeholder")

    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("LAKEHOUSE_API_KEY", "b" * 32)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("LAKEHOUSE_LOCAL_ROOT", str(tmp_path))
    get_settings.cache_clear()

    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/ready")
    get_settings.cache_clear()

    assert response.status_code == HttpStatus.HTTP_200_OK
    assert response.json()["status"] == "ready"
