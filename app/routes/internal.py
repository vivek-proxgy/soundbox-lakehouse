"""Internal operational endpoints — not for end-user clients."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config.settings import get_settings
from app.core.enums.error_key import ErrorKey
from app.core.exception_guard import run_safe
from app.core.logging import get_logger
from app.security.auth import AuthContext
from app.security.dependencies import require_privileged_role

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])
logger = get_logger("lakehouse.internal")


class IngestResponse(BaseModel):
    status: str
    summary: dict[str, Any]


@router.post("/ingest")
def trigger_ingestion(
    auth: Annotated[AuthContext, Depends(require_privileged_role)],
) -> IngestResponse:
    def _execute() -> IngestResponse:
        settings = get_settings()
        logger.info("Ingestion triggered by user=%s engine=%s", auth.user_id, settings.ingest_engine)
        from ingestion.run import run as run_job

        summary = run_job(settings)
        return IngestResponse(status="success", summary=summary)

    return run_safe(_execute, log_context="internal.ingest", error_key=ErrorKey.SERVICE)
