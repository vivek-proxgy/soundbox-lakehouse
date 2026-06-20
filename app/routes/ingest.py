"""Ingestion control API router."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config.settings import get_settings

router = APIRouter()


class IngestResponse(BaseModel):
    status: str
    summary: dict[str, Any]


@router.post("/ingest", response_model=IngestResponse)
async def trigger_ingestion() -> IngestResponse:
    """Manually trigger the ingestion job based on current INGEST_ENGINE and environment settings."""
    settings = get_settings()
    try:
        print(f"[api-server] Triggering ingestion job using engine '{settings.ingest_engine}'...")
        from ingestion.run import run as run_job
        summary = run_job(settings)
        return IngestResponse(status="success", summary=summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion job failed: {e}")
