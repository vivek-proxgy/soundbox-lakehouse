"""Read soundbox-backend Postgres — incremental or full export via env."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import psycopg2

from app.config.settings import Settings, get_settings
from app.ingestion.queries import EXPORT_TABLES, TableExportSpec
from app.ingestion.watermark_store import read_watermark, write_watermark
from app.utils.decryption import decrypt_field


def _connect(settings: Settings):
    settings.require_database()
    connect_kwargs: dict[str, Any] = {
        "host": settings.database_host,
        "port": settings.database_port,
        "user": settings.database_username,
        "password": settings.database_password,
        "dbname": settings.database_name,
    }
    if settings.database_ssl_enabled:
        connect_kwargs["sslmode"] = "require"
    print(
        f"[postgres] Connecting to {settings.database_host}:"
        f"{settings.database_port}/{settings.database_name}"
    )
    return psycopg2.connect(**connect_kwargs)


def _apply_watermark(sql: str, watermark_column: str | None, since: datetime | None) -> str:
    if since is None or not watermark_column:
        return sql.strip()
    return f"{sql.strip()}\n  AND {watermark_column} > %s"


def _decrypt_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = df[column].apply(decrypt_field)
    return df


def export_table(
    spec: TableExportSpec,
    settings: Settings | None = None,
) -> pd.DataFrame:
    cfg = settings or get_settings()
    since: datetime | None = None
    if cfg.ingest_mode == "incremental" and spec.watermark_column:
        since = read_watermark(spec.name, cfg)

    sql = _apply_watermark(spec.sql, spec.watermark_column, since)
    conn = _connect(cfg)
    try:
        if since is not None:
            df = pd.read_sql(sql, conn, params=[since])
        else:
            df = pd.read_sql(sql, conn)
    finally:
        conn.close()

    if df.empty:
        print(f"[postgres] {spec.name}: 0 rows")
        return df

    df = _decrypt_columns(df, spec.decrypt_columns)

    if (
        cfg.ingest_mode == "incremental"
        and spec.watermark_column
        and spec.watermark_column in df.columns
    ):
        latest = pd.to_datetime(df[spec.watermark_column]).max()
        if pd.notna(latest):
            write_watermark(spec.name, latest.to_pydatetime(), cfg)

    print(f"[postgres] {spec.name}: {len(df):,} rows")
    return df


def export_all_tables(settings: Settings | None = None) -> dict[str, pd.DataFrame]:
    cfg = settings or get_settings()
    frames: dict[str, pd.DataFrame] = {}
    for spec in EXPORT_TABLES:
        frames[spec.name] = export_table(spec, cfg)
    return frames
