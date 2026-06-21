"""Global exception handlers — HTTPException-first, no raw 500s."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.enums.error_key import ErrorKey
from app.core.http_errors import normalize_http_exception_detail
from app.core.http_status import HttpStatus
from app.core.messages.error_messages import ErrorMessage
from app.core.responses import build_error_response, format_validation_errors

logger = logging.getLogger("lakehouse.errors")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> Any:
        errors = format_validation_errors(list(exc.errors()))
        return _json(
            HttpStatus.HTTP_400_BAD_REQUEST,
            build_error_response(
                HttpStatus.HTTP_400_BAD_REQUEST,
                errors,
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> Any:
        body = normalize_http_exception_detail(exc.status_code, exc.detail)
        body["request_id"] = _request_id(request)
        return _json(exc.status_code, body)

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_handler(
        request: Request, exc: StarletteHTTPException
    ) -> Any:
        body = normalize_http_exception_detail(exc.status_code, exc.detail)
        body["request_id"] = _request_id(request)
        return _json(exc.status_code, body)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> Any:
        logger.warning("ValueError path=%s message=%s", request.url.path, exc)
        return _json(
            HttpStatus.HTTP_400_BAD_REQUEST,
            build_error_response(
                HttpStatus.HTTP_400_BAD_REQUEST,
                {ErrorKey.VALIDATION.value: str(exc)},
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> Any:
        logger.exception(
            "Unhandled exception path=%s request_id=%s",
            request.url.path,
            _request_id(request),
        )
        return _json(
            HttpStatus.HTTP_400_BAD_REQUEST,
            build_error_response(
                HttpStatus.HTTP_400_BAD_REQUEST,
                {ErrorKey.ERROR.value: ErrorMessage.GENERIC_FAILURE.value},
                request_id=_request_id(request),
            ),
        )


def _json(status_code: int, content: dict[str, Any]) -> Any:
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content=content)
