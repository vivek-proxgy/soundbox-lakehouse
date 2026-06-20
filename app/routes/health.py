"""Health check API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.config.settings import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """System health check endpoint."""
    settings = get_settings()
    return {
        "status": "healthy",
        "engine": settings.ingest_engine,
        "mode": settings.ingest_mode,
        "warehouse": settings.warehouse_uri,
    }
