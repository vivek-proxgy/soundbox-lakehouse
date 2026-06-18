"""DuckDB helpers — query local or GCS parquet (soundbox-chanakya pattern)."""

from __future__ import annotations

import glob
from pathlib import Path

import duckdb

from app.config.settings import get_settings

ParquetTable = str

_TABLE_SUBDIRS: dict[str, tuple[str, ...]] = {
    "merchants": ("merchants_full", "merchants"),
    "transactions": ("raw_transactions", "transactions"),
    "device_telemetry": ("device_telemetry",),
}


def _local_root() -> Path:
    return Path(get_settings().lakehouse_local_root)


def resolve_parquet_glob(table: ParquetTable) -> str:
    root = _local_root()
    for subdir in _TABLE_SUBDIRS.get(table, (table,)):
        pattern = str(root / subdir / "*.parquet")
        if glob.glob(pattern):
            return pattern
    raise FileNotFoundError(f"No parquet for '{table}' under {root}. Run the ingestion job first.")


def resolve_parquet_glob_optional(table: ParquetTable) -> str | None:
    try:
        return resolve_parquet_glob(table)
    except FileNotFoundError:
        return None


def get_duckdb_connection() -> duckdb.DuckDBPyConnection:
    threads = get_settings().duckdb_threads
    conn = duckdb.connect()
    conn.execute(f"PRAGMA threads={max(1, threads)}")
    return conn


def query_parquet_glob(glob_path: str | Path, sql: str) -> list[tuple]:
    path = str(glob_path)
    conn = get_duckdb_connection()
    try:
        conn.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM read_parquet('{path}')")
        return conn.execute(sql).fetchall()
    finally:
        conn.close()
