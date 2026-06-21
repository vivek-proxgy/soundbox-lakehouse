"""Copilot sub-router — stateless; conversation history owned by soundbox-backend."""

from __future__ import annotations

import io
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.enums.error_key import ErrorKey
from app.core.exception_guard import run_safe
from app.routes.schemas.copilot import (
    CopilotQueryRequest,
    CopilotQueryResponse,
    ExportExcelRequest,
    ExportPDFRequest,
)
from app.security.auth import AuthContext
from app.security.dependencies import require_auth
from app.services.copilot import CopilotService

router = APIRouter(tags=["copilot"])

_copilot_service: CopilotService | None = None


def get_copilot_service() -> CopilotService:
    global _copilot_service
    if _copilot_service is None:
        _copilot_service = CopilotService()
    return _copilot_service


@router.post("/query", response_model=CopilotQueryResponse)
def query_copilot(
    req: CopilotQueryRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> CopilotQueryResponse:
    """
    Process copilot query. Backend MUST send conversation_history on every turn.
    This service does not store sessions — fully stateless for Cloud Run scale-out.
    """

    def _execute() -> CopilotQueryResponse:
        service = get_copilot_service()
        history_payload = [msg.model_dump() for msg in req.conversation_history]
        result = service.query(
            prompt=req.prompt,
            conversation_id=req.conversation_id,
            conversation_history=history_payload,
            org_id=req.org_id,
            model_name=req.model_name,
            limit=req.limit,
            offset=req.offset,
        )
        return CopilotQueryResponse(**result)

    return run_safe(_execute, log_context="copilot.query", error_key=ErrorKey.SERVICE)


@router.post("/export/excel")
def export_excel_report(
    req: ExportExcelRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
):
    def _execute() -> StreamingResponse:
        service = get_copilot_service()
        excel_bytes = service.generate_excel_report(req.data)
        filename = f"report_{req.filename_hint or 'export'}.xlsx"
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return run_safe(_execute, log_context="copilot.export_excel", error_key=ErrorKey.SERVICE)


@router.post("/export/pdf")
def export_pdf_report(
    req: ExportPDFRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
):
    def _execute() -> StreamingResponse:
        service = get_copilot_service()
        pdf_bytes = service.generate_pdf_report(req.answer, req.data or [])
        filename = f"report_{req.filename_hint or 'export'}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return run_safe(_execute, log_context="copilot.export_pdf", error_key=ErrorKey.SERVICE)
