"""Health check API router."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.core.http_status import HttpStatus
from app.services.health_service import build_readiness_report

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str | bool]:
    """Liveness probe — public, no auth required."""
    settings = get_settings()
    auth_ready = bool(
        settings.lakehouse_api_key
        or settings.auth_jwt_secret
        or not settings.auth_enabled
    )
    return {
        "status": "healthy",
        "service": "soundbox-intelligence",
        "engine": settings.ingest_engine,
        "mode": settings.ingest_mode,
        "auth_configured": auth_ready,
    }


@router.get("/ready")
def readiness_check():
    """Readiness probe — validates auth, Gemini, and parquet availability."""
    settings = get_settings()
    report = build_readiness_report(settings)
    status_code = (
        HttpStatus.HTTP_200_OK
        if report["status"] == "ready"
        else HttpStatus.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=status_code, content=report)
