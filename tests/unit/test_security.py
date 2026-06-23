"""Tests for SQL security, auth, and exception handling."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.core.enums.error_key import ErrorKey
from app.core.http_status import HttpStatus
from app.core.sql_security import sanitize_sql, sanitize_org_id
from app.server import create_app

import secrets
TEST_JWT_SECRET = f"mock-jwt-secret-{secrets.token_hex(16)}"
TEST_LAKEHOUSE_API_KEY = f"mock-api-key-{secrets.token_hex(16)}"


def test_sanitize_sql_blocks_destructive_keywords():
    with pytest.raises(HTTPException) as exc_info:
        sanitize_sql("DROP TABLE merchants")
    assert exc_info.value.status_code == HttpStatus.HTTP_400_BAD_REQUEST

    with pytest.raises(HTTPException):
        sanitize_sql("DELETE FROM transactions")

    assert sanitize_sql("SELECT count(*) FROM merchants") == "SELECT count(*) FROM merchants"


def test_sanitize_sql_requires_select():
    with pytest.raises(HTTPException) as exc_info:
        sanitize_sql("SHOW TABLES")
    assert ErrorKey.SQL.value in exc_info.value.detail["errors"]


def test_sanitize_org_id_strips_unsafe_chars():
    assert sanitize_org_id("org-123_abc") == "org-123_abc"
    assert sanitize_org_id("org'; DROP TABLE--") == "orgDROPTABLE--"


def _make_token(secret: str, *, expired: bool = False) -> str:
    payload = {
        "id": "user-1",
        "sessionId": "sess-1",
        "type": "access",
        "sub": "user-1",
        "exp": int(time.time()) + (-60 if expired else 3600),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    client = TestClient(create_app(), raise_server_exceptions=False)
    yield client
    get_settings.cache_clear()


def test_health_is_public(auth_client: TestClient):
    response = auth_client.get("/health")
    assert response.status_code == HttpStatus.HTTP_200_OK
    assert response.json()["status"] == "healthy"


def test_protected_route_requires_auth(auth_client: TestClient):
    response = auth_client.post("/api/v1/intelligence/sql", json={"sql": "SELECT 1"})
    assert response.status_code == HttpStatus.HTTP_401_UNAUTHORIZED
    body = response.json()
    assert body["status"] == HttpStatus.HTTP_401_UNAUTHORIZED
    assert ErrorKey.AUTH.value in body["errors"]


def test_jwt_auth_allows_readonly_sql(auth_client: TestClient):
    token = _make_token(TEST_JWT_SECRET)
    response = auth_client.post(
        "/api/v1/intelligence/sql",
        json={"sql": "SELECT 1 as n"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code != HttpStatus.HTTP_401_UNAUTHORIZED


def test_expired_jwt_rejected(auth_client: TestClient):
    token = _make_token(TEST_JWT_SECRET, expired=True)
    response = auth_client.post(
        "/api/v1/intelligence/sql",
        json={"sql": "SELECT 1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == HttpStatus.HTTP_401_UNAUTHORIZED
    assert "expired" in response.json()["errors"][ErrorKey.AUTH.value].lower()


def test_api_key_auth(auth_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LAKEHOUSE_API_KEY", TEST_LAKEHOUSE_API_KEY)
    get_settings.cache_clear()
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/v1/intelligence/sql",
        json={"sql": "SELECT 1"},
        headers={"X-API-Key": TEST_LAKEHOUSE_API_KEY},
    )
    assert response.status_code != HttpStatus.HTTP_401_UNAUTHORIZED


def test_api_key_only_rejects_jwt(auth_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_API_KEY_ONLY", "true")
    monkeypatch.setenv("LAKEHOUSE_API_KEY", TEST_LAKEHOUSE_API_KEY)
    get_settings.cache_clear()
    client = TestClient(create_app(), raise_server_exceptions=False)
    token = _make_token(TEST_JWT_SECRET)

    response = client.post(
        "/api/v1/intelligence/sql",
        json={"sql": "SELECT 1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == HttpStatus.HTTP_401_UNAUTHORIZED
    get_settings.cache_clear()


def test_unhandled_exception_returns_400_not_500(auth_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    token = _make_token(TEST_JWT_SECRET)

    def boom(*_args, **_kwargs):
        raise RuntimeError("internal boom")

    monkeypatch.setattr("app.routes.intelligence.get_services", boom)
    response = auth_client.post(
        "/api/v1/intelligence/ask",
        json={"prompt": "how many merchants"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == HttpStatus.HTTP_400_BAD_REQUEST
    assert response.json()["status"] == HttpStatus.HTTP_400_BAD_REQUEST
    assert ErrorKey.ERROR.value in response.json()["errors"]
