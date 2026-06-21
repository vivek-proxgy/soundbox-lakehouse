"""Optional integration tests — require a running lakehouse API."""

from __future__ import annotations

import os

import httpx
import pytest

from app.config.enums.env_var import SettingsEnv

pytestmark = pytest.mark.skipif(
    os.environ.get(SettingsEnv.INTEGRATION_TEST) != "true",
    reason=(
        f"Set {SettingsEnv.INTEGRATION_TEST}=true with "
        f"{SettingsEnv.LAKEHOUSE_BASE_URL} and {SettingsEnv.LAKEHOUSE_API_KEY}"
    ),
)


@pytest.fixture
def lakehouse_client():
    base_url = os.environ[SettingsEnv.LAKEHOUSE_BASE_URL].rstrip("/")
    api_key = os.environ[SettingsEnv.LAKEHOUSE_API_KEY]
    return base_url, api_key


def test_lakehouse_ready_probe(lakehouse_client):
    base_url, _ = lakehouse_client
    response = httpx.get(f"{base_url}/ready", timeout=30)
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_lakehouse_copilot_query(lakehouse_client):
    base_url, api_key = lakehouse_client
    response = httpx.post(
        f"{base_url}/api/v1/intelligence/copilot/query",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json={"prompt": "How many merchants?", "conversation_history": []},
        timeout=120,
    )
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
