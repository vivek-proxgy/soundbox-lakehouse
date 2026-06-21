"""Tests for exception guard helper."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.enums.error_key import ErrorKey
from app.core.exception_guard import run_safe
from app.core.http_status import HttpStatus


def test_run_safe_returns_value():
    assert run_safe(lambda: 42) == 42


def test_run_safe_re_raises_http_exception():
    def fail() -> None:
        raise HTTPException(status_code=HttpStatus.HTTP_404_NOT_FOUND, detail="missing")

    with pytest.raises(HTTPException) as exc_info:
        run_safe(fail)
    assert exc_info.value.status_code == HttpStatus.HTTP_404_NOT_FOUND


def test_run_safe_wraps_generic_exception():
    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(HTTPException) as exc_info:
        run_safe(fail, error_key=ErrorKey.SERVICE)
    assert exc_info.value.status_code == HttpStatus.HTTP_400_BAD_REQUEST
    assert ErrorKey.SERVICE.value in exc_info.value.detail["errors"]
