"""FastAPI router for Soundbox Chanakya Copilot endpoints."""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.copilot import CopilotService

router = APIRouter(prefix="/api/v1/copilot", tags=["copilot"])

# Lazy loaded service
_copilot_service: CopilotService | None = None


def get_copilot_service() -> CopilotService:
    """Lazy load CopilotService to optimize startup imports."""
    global _copilot_service
    if _copilot_service is None:
        _copilot_service = CopilotService()
    return _copilot_service


# =====================================================================
# Request / Response Schemas
# =====================================================================

class CopilotQueryRequest(BaseModel):
    prompt: str = Field(..., description="The user question to process.")
    session_id: Optional[str] = Field(None, description="Optional unique identifier for the conversation session.")
    org_id: Optional[str] = Field(None, description="Optional organization filter.")
    model_name: Optional[str] = Field(None, description="Optional name of the Gemini model to invoke (e.g. gemini-2.5-flash).")
    limit: Optional[int] = Field(100, description="The maximum number of rows to return.")
    offset: Optional[int] = Field(0, description="The starting offset for results.")


class MerchantReference(BaseModel):
    id: str
    name: str


class CopilotQueryResponse(BaseModel):
    session_id: str
    answer: str
    intent: str
    sources: List[str]
    suggestions: List[str]
    latency: float
    sql_query: Optional[str] = Field(None, description="The SQL query executed, if any.")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Raw query result records, if any.")
    merchant_references: List[MerchantReference]
    merchant_lookup: List[Dict[str, Any]]
    pagination: Optional[Dict[str, Any]] = Field(None, description="Pagination metadata (limit, offset, total_count, has_more).")


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class CopilotHistoryResponse(BaseModel):
    session_id: str
    history: List[ChatMessage]


class ExportExcelRequest(BaseModel):
    data: List[Dict[str, Any]] = Field(..., description="The raw JSON data records to export.")
    session_id: Optional[str] = Field(None, description="Optional session ID for filename.")


class ExportPDFRequest(BaseModel):
    answer: str = Field(..., description="The text response markdown to convert.")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Optional raw query data rows.")
    session_id: Optional[str] = Field(None, description="Optional session ID for filename.")


# =====================================================================
# API Endpoints
# =====================================================================

@router.post("/query", response_model=CopilotQueryResponse)
async def query_copilot(req: CopilotQueryRequest) -> CopilotQueryResponse:
    """Submit a question to the operational copilot.
    
    The copilot classifies query intent, retrieves context from DuckDB views, and synthesizes 
    an answer (using Google Gemini if available, or structured fallback templates).
    """
    try:
        service = get_copilot_service()
        result = service.query(
            prompt=req.prompt,
            session_id=req.session_id,
            org_id=req.org_id,
            model_name=req.model_name,
            limit=req.limit,
            offset=req.offset
        )
        return CopilotQueryResponse(**result)
    except Exception as e:
        print(f"[copilot-router] Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Copilot query failed: {str(e)}")


@router.get("/history", response_model=CopilotHistoryResponse)
async def get_copilot_history(session_id: str = Query(..., description="The session identifier.")) -> CopilotHistoryResponse:
    """Retrieve chat history (recent messages) for a given session."""
    try:
        service = get_copilot_service()
        history = service.get_history(session_id)
        # Convert history dict format to ChatMessage objects
        messages = [
            ChatMessage(role=msg["role"], content=msg["content"], timestamp=msg["timestamp"])
            for msg in history
        ]
        return CopilotHistoryResponse(session_id=session_id, history=messages)
    except Exception as e:
        print(f"[copilot-router] History retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load chat history: {str(e)}")


@router.delete("/session/{session_id}", response_model=Dict[str, Any])
async def delete_copilot_session(session_id: str) -> Dict[str, Any]:
    """Terminate a chat session and delete its conversation history from storage."""
    try:
        service = get_copilot_service()
        service.terminate_session(session_id)
        return {"status": "success", "message": f"Session {session_id} terminated and deleted."}
    except Exception as e:
        print(f"[copilot-router] Session deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.post("/export/excel")
async def export_excel_report(req: ExportExcelRequest):
    """Generate and stream a downloadable Excel spreadsheet of query data records."""
    try:
        service = get_copilot_service()
        excel_bytes = service.generate_excel_report(req.data)
        
        filename = f"report_{req.session_id or 'export'}.xlsx"
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"[copilot-router] Excel export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel report: {str(e)}")


@router.post("/export/pdf")
async def export_pdf_report(req: ExportPDFRequest):
    """Generate and stream a downloadable styled PDF document of query insights and data."""
    try:
        service = get_copilot_service()
        pdf_bytes = service.generate_pdf_report(req.answer, req.data or [])
        
        filename = f"report_{req.session_id or 'export'}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"[copilot-router] PDF export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")
