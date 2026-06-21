"""Audit logging for intelligence and internal mutation endpoints."""

from __future__ import annotations

import logging
from typing import Callable

from starlette.requests import Request
from starlette.responses import Response

from app.routes.enums.api_path import ApiPath

logger = logging.getLogger("lakehouse.audit")


def _is_auditable(request: Request) -> bool:
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        return True
    return any(fragment in request.url.path for fragment in ApiPath.audit_path_fragments())


async def audit_middleware(request: Request, call_next: Callable) -> Response:
    response = await call_next(request)

    if not _is_auditable(request):
        return response

    try:
        user_id = getattr(request.state, "user_id", None)
        org_id = getattr(request.state, "org_id", None)
        logger.info(
            "audit_event user=%s org=%s method=%s path=%s status=%s request_id=%s",
            user_id,
            org_id,
            request.method,
            request.url.path,
            response.status_code,
            getattr(request.state, "request_id", None),
        )
    except Exception as exc:
        logger.warning("Audit logging failed: %s", exc)

    return response
