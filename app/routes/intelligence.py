"""Backend-facing intelligence API — consumed by on-prem-soundbox-backend."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config.settings import get_settings
from app.core.enums.error_key import ErrorKey
from app.core.exception_guard import run_safe
from app.core.http_errors import service_unavailable
from app.core.messages.error_messages import ErrorMessage
from app.core.sql_security import sanitize_sql
from app.routes import copilot as copilot_routes
from app.security.auth import AuthContext
from app.security.dependencies import require_auth
from app.services.ai_service import AIService
from app.services.duckdb_service import DuckDBService

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

_duckdb_svc: DuckDBService | None = None
_ai_svc: AIService | None = None


def get_services() -> tuple[DuckDBService, AIService]:
    global _duckdb_svc, _ai_svc
    if _duckdb_svc is None:
        settings = get_settings()
        _duckdb_svc = DuckDBService(settings)
        _ai_svc = AIService(settings, _duckdb_svc)
    return _duckdb_svc, _ai_svc


class IntelligenceAskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    org_id: str | None = Field(None, max_length=64)


class IntelligenceSqlRequest(BaseModel):
    sql: str = Field(..., min_length=1)


class IntelligenceAskResponse(BaseModel):
    answer: str
    sql: str
    data: list[dict[str, Any]]
    count: int


class IntelligenceSqlResponse(BaseModel):
    sql: str
    data: list[dict[str, Any]]
    count: int


@router.post("/ask", response_model=IntelligenceAskResponse)
def ask_intelligence(
    req: IntelligenceAskRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> IntelligenceAskResponse:
    """Natural-language intelligence query for soundbox-backend to forward."""

    def _execute() -> IntelligenceAskResponse:
        _, ai_svc = get_services()
        if not ai_svc.is_configured():
            raise service_unavailable(ErrorKey.CONFIG, ErrorMessage.GEMINI_NOT_CONFIGURED.value)

        result = ai_svc.query_with_ai(req.prompt)
        records = result.get("data", [])
        return IntelligenceAskResponse(
            answer=result.get("answer", ""),
            sql=result.get("sql", ""),
            data=records,
            count=len(records),
        )

    return run_safe(_execute, log_context="intelligence.ask")


@router.post("/sql", response_model=IntelligenceSqlResponse)
def query_sql(
    req: IntelligenceSqlRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> IntelligenceSqlResponse:
    """Read-only SQL against lakehouse views — backend-internal analytics."""

    def _execute() -> IntelligenceSqlResponse:
        safe_sql = sanitize_sql(req.sql)
        duckdb_svc, _ = get_services()
        df = duckdb_svc.query_to_df(safe_sql)
        records = df.to_dict(orient="records")
        return IntelligenceSqlResponse(sql=safe_sql, data=records, count=len(records))

    return run_safe(_execute, log_context="intelligence.sql", error_key=ErrorKey.SQL)


router.include_router(
    copilot_routes.router,
    prefix="/copilot",
)
