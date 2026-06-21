"""HTTP error factory — mirrors on-prem-soundbox-backend createHttpError()."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core.enums.error_key import ErrorKey
from app.core.http_status import HttpStatus


def create_http_exception(
    error_key: ErrorKey,
    message: str,
    status_code: int,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "status": status_code,
            "errors": {error_key.value: message},
        },
    )


def bad_request(error_key: ErrorKey, message: str) -> HTTPException:
    return create_http_exception(error_key, message, HttpStatus.HTTP_400_BAD_REQUEST)


def unauthorized(message: str) -> HTTPException:
    return create_http_exception(ErrorKey.AUTH, message, HttpStatus.HTTP_401_UNAUTHORIZED)


def forbidden(message: str) -> HTTPException:
    return create_http_exception(ErrorKey.FORBIDDEN, message, HttpStatus.HTTP_403_FORBIDDEN)


def not_found(message: str) -> HTTPException:
    return create_http_exception(ErrorKey.NOT_FOUND, message, HttpStatus.HTTP_404_NOT_FOUND)


def conflict(message: str) -> HTTPException:
    return create_http_exception(ErrorKey.CONFLICT, message, HttpStatus.HTTP_409_CONFLICT)


def rate_limited(message: str) -> HTTPException:
    return create_http_exception(ErrorKey.RATE_LIMIT, message, HttpStatus.HTTP_429_TOO_MANY_REQUESTS)


def service_unavailable(error_key: ErrorKey, message: str) -> HTTPException:
    return create_http_exception(error_key, message, HttpStatus.HTTP_503_SERVICE_UNAVAILABLE)


def error_key_for_status(status_code: int) -> ErrorKey:
    mapping: dict[int, ErrorKey] = {
        HttpStatus.HTTP_401_UNAUTHORIZED: ErrorKey.AUTH,
        HttpStatus.HTTP_403_FORBIDDEN: ErrorKey.FORBIDDEN,
        HttpStatus.HTTP_404_NOT_FOUND: ErrorKey.NOT_FOUND,
        HttpStatus.HTTP_409_CONFLICT: ErrorKey.CONFLICT,
        HttpStatus.HTTP_429_TOO_MANY_REQUESTS: ErrorKey.RATE_LIMIT,
    }
    return mapping.get(status_code, ErrorKey.ERROR)


def normalize_http_exception_detail(
    status_code: int,
    detail: Any,
) -> dict[str, Any]:
    if isinstance(detail, dict) and "errors" in detail and "status" in detail:
        return detail
    message = str(detail)
    error_key = error_key_for_status(status_code)
    return {
        "status": status_code,
        "errors": {error_key.value: message},
    }
