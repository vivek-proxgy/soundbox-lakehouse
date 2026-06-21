"""FastAPI server exposing AI, DuckDB, and Ingestion APIs."""

from __future__ import annotations

from fastapi import FastAPI
from app.routes import health, ingest, query, copilot

app = FastAPI(
    title="Soundbox Lakehouse API Server",
    description="APIs for querying GCS/local parquet datasets using Gemini and DuckDB, and running ingestion.",
    version="1.0.0",
)

# Include modular routers
app.include_router(health.router)
app.include_router(ingest.router, tags=["ingestion"])
app.include_router(query.router, tags=["ai-duckdb"])
app.include_router(copilot.router)


