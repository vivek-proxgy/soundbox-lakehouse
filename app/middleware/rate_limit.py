"""In-memory rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.routes.enums.api_path import ApiPath
from app.security.enums.api_header import ApiHeader
from app.core.enums.error_key import ErrorKey
from app.core.http_status import HttpStatus
from app.core.messages.error_messages import ErrorMessage
from app.core.responses import build_error_response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limit: int, window_seconds: int) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in ApiPath.rate_limit_exempt_paths():
            return await call_next(request)

        client_key = request.headers.get(ApiHeader.API_KEY.value)
        if not client_key:
            client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()

        with self._lock:
            window = self._hits[client_key]
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= self.limit:
                request_id = getattr(request.state, "request_id", None)
                return JSONResponse(
                    status_code=HttpStatus.HTTP_429_TOO_MANY_REQUESTS,
                    content=build_error_response(
                        HttpStatus.HTTP_429_TOO_MANY_REQUESTS,
                        {ErrorKey.RATE_LIMIT.value: ErrorMessage.RATE_LIMIT.value},
                        request_id=request_id,
                    ),
                    headers={"Retry-After": str(self.window_seconds)},
                )

            window.append(now)

        return await call_next(request)
