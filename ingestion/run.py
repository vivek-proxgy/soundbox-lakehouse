"""Orchestrator to run the configured ingestion engine (Pandas or PySpark)."""

from __future__ import annotations

from app.config.settings import Settings, get_settings


def run(settings: Settings | None = None) -> dict:
    cfg = settings or get_settings()
    if cfg.ingest_engine == "spark":
        from ingestion.spark_engine import run as run_spark
        return run_spark(cfg)
    else:
        from ingestion.pandas_engine import run as run_pandas
        return run_pandas(cfg)
