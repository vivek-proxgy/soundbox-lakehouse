"""Copilot request/response schemas — stateless conversation model."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HierarchyScopeFilter(BaseModel):
    column: Literal["head_office_id", "zone_office_id", "regional_office_id", "branch_office_id"]
    taxonomy_id: str = Field(..., max_length=64)


class AccessScope(BaseModel):
    organization_id: str = Field(..., max_length=64)
    roles: List[str] = Field(default_factory=list)
    can_view_pii: bool = False
    hierarchy_enabled: bool = False
    hierarchy_filter: Optional[HierarchyScopeFilter] = None


class ConversationMessage(BaseModel):
    """Single turn supplied by soundbox-backend; never persisted by intelligence service."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class CopilotQueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Opaque ID owned by soundbox-backend for correlation and audit only.",
    )
    conversation_history: List[ConversationMessage] = Field(
        default_factory=list,
        max_length=20,
        description="Prior turns sent by backend each request — stateless, not stored here.",
    )
    org_id: Optional[str] = Field(None, max_length=64)
    access_scope: Optional[AccessScope] = Field(
        None,
        description="Authoritative caller scope from soundbox-backend (org, role, hierarchy).",
    )
    model_name: Optional[str] = Field(None, max_length=64)
    limit: Optional[int] = Field(100, ge=1, le=1000)
    offset: Optional[int] = Field(0, ge=0)


class CopilotQueryResponse(BaseModel):
    conversation_id: Optional[str] = None
    answer: str
    intent: str
    sources: List[str]
    suggestions: List[str]
    latency: float
    sql_query: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    merchant_references: List[Dict[str, str]]
    merchant_lookup: List[Dict[str, Any]]
    pagination: Optional[Dict[str, Any]] = None


class ExportExcelRequest(BaseModel):
    data: List[Dict[str, Any]] = Field(...)
    filename_hint: Optional[str] = Field(None, max_length=128)


class ExportPDFRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=50000)
    data: Optional[List[Dict[str, Any]]] = None
    filename_hint: Optional[str] = Field(None, max_length=128)
