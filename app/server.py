"""FastAPI application factory — Soundbox Intelligence Service (backend AI layer)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import Settings, get_settings
from app.core.startup_validation import validate_server_startup
from app.security.enums.api_header import ApiHeader
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import setup_logging
from app.middleware.audit import audit_middleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routes import build_api_router
from app.security.dependencies import get_auth_context


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    validate_server_startup(settings)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    app = FastAPI(
        title="Soundbox Intelligence Service",
        description=(
            "Backend AI intelligence layer for on-prem-soundbox-backend. "
            "Provides natural-language analytics, copilot, and read-only SQL over the lakehouse."
        ),
        version="2.0.0",
        lifespan=lifespan,
        dependencies=[Depends(get_auth_context)],
    )

    register_exception_handlers(app)

    if cfg.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.allowed_origins_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            allow_headers=[
                ApiHeader.AUTHORIZATION.value,
                "Content-Type",
                ApiHeader.API_KEY.value,
                ApiHeader.REQUEST_ID.value,
            ],
        )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        limit=cfg.throttle_limit,
        window_seconds=cfg.throttle_ttl,
    )
    app.add_middleware(RequestContextMiddleware)
    app.middleware("http")(audit_middleware)

    app.include_router(build_api_router())
    return app
