"""Backward-compatible re-exports — prefer app.utils.data_access."""

from app.utils.data_access import get_duckdb_connection, query_parquet_glob

__all__ = ["get_duckdb_connection", "query_parquet_glob"]
