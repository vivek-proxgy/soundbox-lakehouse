"""AI and SQL Query API router."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config.settings import get_settings
from app.services.ai_service import AIService
from app.services.duckdb_service import DuckDBService

router = APIRouter()

# Lazy loaded services
_duckdb_svc = None
_ai_svc = None


def get_services() -> tuple[DuckDBService, AIService]:
    """Lazy load services to optimize startup and import behaviors."""
    global _duckdb_svc, _ai_svc
    if _duckdb_svc is None:
        settings = get_settings()
        _duckdb_svc = DuckDBService(settings)
        _ai_svc = AIService(settings, _duckdb_svc)
    return _duckdb_svc, _ai_svc


class QueryRequest(BaseModel):
    prompt: str


class SQLRequest(BaseModel):
    sql: str


@router.post("/query", response_model=dict[str, Any])
async def query_endpoint(req: QueryRequest) -> dict[str, Any]:
    """Submit a natural language question. The AI will write/run SQL and synthesize an answer."""
    try:
        _, ai_svc = get_services()
        result = ai_svc.query_with_ai(req.prompt)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sql", response_model=dict[str, Any])
async def sql_endpoint(req: SQLRequest) -> dict[str, Any]:
    """Directly execute a DuckDB SQL query against the deduplicated parquet views."""
    try:
        duckdb_svc, _ = get_services()
        df = duckdb_svc.query_to_df(req.sql)
        records = df.to_dict(orient="records")
        return {
            "sql": req.sql,
            "data": records,
            "count": len(records),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
